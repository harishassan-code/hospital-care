"""Ambulance rules: the registry (story #50) and trips (story #51). A trip sends an available ambulance from
its base hospital to carry an approved transfer, and steps it through the road (depart, arrive, complete).
Every write is one transaction that locks the transfer, then the trip or the ambulance, and audit-logs
each change."""

from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role
from apps.accounts.permissions import can_edit, may_change
from apps.audit.services import record
from apps.matching.distance import estimated_travel_minutes, hospital_distance
from apps.resources.services import change_status
from apps.resources.state_machine import TransitionNotAllowed
from apps.transfers.services import dispatch as dispatch_transfer
from apps.transfers.services import lock_transfer, start_transit

from .models import AMBULANCE_LIFECYCLE, TRIP_LIFECYCLE, TRIP_ONLY_ACTIONS, Ambulance, Trip

TAKEN = "This asset tag is already registered at this hospital."
# The audit word for each step, e.g. trip.departed.
STEP_AUDIT = {"depart": "departed", "arrive": "arrived", "complete": "completed"}
STEP_STAMP = {"depart": "departed_at", "arrive": "arrived_at", "complete": "completed_at"}


# ── Who sees and who may act ──────────────────────────────────────────────────────────────────────


def visible_ambulances(user):
    """The ambulances the user may see: their hospital's, or all of them for admins (story #50)."""
    items = Ambulance.objects.all()
    if user.effective_role == Role.ADMIN:
        return items
    return items.filter(hospital_id=user.hospital_id) if user.hospital_id else items.none()


def may_dispatch_trip(user, transfer) -> bool:
    """Edit on `ambulances` at the supplying hospital (admins: any). Every trip step needs the same (story
    #51)."""
    role = user.effective_role
    return can_edit(role, "ambulances") and (role == Role.ADMIN or user.hospital_id == transfer.supplier_id)


def may_step_trip(user, trip: Trip) -> bool:
    return may_dispatch_trip(user, trip.transfer)


def trip_actions_for(user, trip: Trip) -> list[str]:
    """The steps the user may take on this trip now: valid from its status, and allowed to the user."""
    if not may_step_trip(user, trip):
        return []
    return [action for status, action in TRIP_LIFECYCLE.transitions if status == trip.status]


def trip_eta_minutes(supplier, receiver) -> int:
    """The estimated driving time from the supplying hospital to the receiving one, in whole minutes.
    Simulated from hospital coordinates (apps.matching.distance); no live location (story #51)."""
    return round(estimated_travel_minutes(hospital_distance(supplier, receiver)))


# ── Registry (story #50) ──────────────────────────────────────────────────────────────────────────


def register_ambulance(serializer, actor) -> Ambulance:
    """Save a new ambulance at its base hospital and audit-log it. Non-admins register at their own hospital;
    admins choose one (hospitalId) or use their own. Tags are unique per hospital, ignoring case."""
    hospital = serializer.validated_data.get("hospital") if actor.effective_role == Role.ADMIN else None
    hospital = hospital or getattr(actor, "hospital", None)
    if hospital is None:
        raise ValidationError({"hospitalId": ["Pick the base hospital for this ambulance."]})
    identifier = serializer.validated_data["identifier"]
    if Ambulance.objects.filter(hospital=hospital, identifier__iexact=identifier).exists():
        raise ValidationError({"identifier": [TAKEN]})
    try:
        with transaction.atomic():
            ambulance = serializer.save(hospital=hospital)
    except IntegrityError:  # someone registered the same tag at the same moment
        raise ValidationError({"identifier": [TAKEN]}) from None
    record(
        actor,
        "ambulance.registered",
        ambulance,
        after={"identifier": ambulance.identifier, "type": ambulance.type, "status": ambulance.status},
    )
    return ambulance


@transaction.atomic
def apply_ambulance_action(ambulance_id: int, action: str, *, actor, reason: str = "") -> Ambulance:
    """Move an ambulance along its lifecycle, locking the row. Another hospital's ambulance is a 404 for
    users who may not change it (own-hospital rule). Raises TransitionNotAllowed if the move isn't
    allowed. The trip's moves (dispatch, release) are refused here: a trip makes them (story #51)."""
    ambulance = get_object_or_404(Ambulance.objects.select_for_update(), pk=ambulance_id)
    if not may_change(actor, ambulance):
        raise Http404
    if action in TRIP_ONLY_ACTIONS:
        raise TransitionNotAllowed("A trip moves this vehicle. Use the transfer's trip instead.")
    return change_status(ambulance, action, actor=actor, reason=reason)


# ── Trips (story #51) ─────────────────────────────────────────────────────────────────────────────


def trips_with_details():
    """Trips with what the API shows loaded: the transfer, the ambulance and who dispatched it."""
    return Trip.objects.select_related("transfer", "ambulance", "dispatched_by")


@transaction.atomic
def dispatch_trip(transfer, *, ambulance_id: int, actor) -> Trip:
    """Send an available ambulance from the supplying hospital to carry an approved transfer. In one
    transaction: lock the transfer, lock the ambulance, move the transfer to dispatched (its own move,
    via_trip), move the ambulance to dispatched, and create the trip with the ETA.

    Refusals, nothing saved: PermissionDenied (403) unless the user may edit ambulances at the supplier;
    Http404 for an ambulance the user can't see; TransferConflict (409) if the transfer isn't approved;
    TransitionNotAllowed (409) if the ambulance isn't available; ValidationError (400) if it isn't based
    at the supplier."""
    if not may_dispatch_trip(actor, transfer):
        raise PermissionDenied(
            "Only staff at the supplying hospital who may edit ambulances can dispatch one."
        )
    locked = lock_transfer(transfer)
    ambulance = visible_ambulances(actor).select_for_update().filter(pk=ambulance_id).first()
    if ambulance is None:
        raise Http404("No ambulance with that id.")
    moved = dispatch_transfer(locked, actor=actor, via_trip=True)
    AMBULANCE_LIFECYCLE.next(ambulance.status, "dispatch")
    if ambulance.hospital_id != moved.supplier_id:
        raise ValidationError(
            {"ambulance": ["Only an ambulance based at the supplying hospital can carry this transfer."]}
        )
    change_status(ambulance, "dispatch", actor=actor, reason=f"Transfer #{moved.pk}")
    try:
        trip = Trip.objects.create(
            transfer=moved,
            ambulance=ambulance,
            eta_minutes=trip_eta_minutes(moved.supplier, moved.receiver),
            dispatched_by=actor,
        )
    except IntegrityError:  # the database's own one-active-trip checks, behind the locks above
        raise TransitionNotAllowed("This transfer or ambulance already has a trip on the road.") from None
    record(
        actor,
        "trip.dispatched",
        trip,
        after={"status": trip.status, "ambulance": ambulance.identifier, "etaMinutes": trip.eta_minutes},
        reason=f"Transfer #{moved.pk}",
    )
    return trip


@transaction.atomic
def step_trip(trip: Trip, action: str, *, actor, note: str = "") -> Trip:
    """Move a trip along its lifecycle: depart (the transfer goes in transit), arrive, complete (the
    ambulance is released; the transfer stays in transit until the receiver confirms it, story #49). Locks
    the transfer, then the trip, then the ambulance. PermissionDenied (403) for a user who may not step
    it; TransitionNotAllowed or TransferConflict (409) when the move isn't allowed now. Nothing is saved
    on a refusal."""
    if not may_step_trip(actor, trip):
        raise PermissionDenied(
            "Only staff at the supplying hospital who may edit ambulances can move a trip."
        )
    transfer = lock_transfer(trip.transfer)
    locked = Trip.objects.select_for_update().select_related("transfer", "ambulance").get(pk=trip.pk)
    before = locked.status
    after = TRIP_LIFECYCLE.next(before, action)
    if action == "depart":
        start_transit(transfer, actor=actor, via_trip=True)
    elif action == "complete":
        ambulance = Ambulance.objects.select_for_update().get(pk=locked.ambulance_id)
        change_status(ambulance, "release", actor=actor, reason=f"Trip #{locked.pk} completed")
    stamp = STEP_STAMP[action]
    setattr(locked, stamp, timezone.now())
    locked.status = after
    locked.save(update_fields=["status", stamp])
    record(
        actor,
        f"trip.{STEP_AUDIT[action]}",
        locked,
        before={"status": before},
        after={"status": after},
        reason=note or action,
    )
    return locked
