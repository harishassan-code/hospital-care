"""Ambulance registry (story #50) and dispatch with trip tracking (story #51). A trip moves its transfer
through the transfer services, in the same transaction, so the two never disagree."""

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.accounts.permissions import may_change
from apps.audit.services import record
from apps.matching.distance import estimated_travel_minutes, haversine_km
from apps.resources.state_machine import TransitionNotAllowed
from apps.transfers import services as transfers
from apps.transfers.models import Transfer

from .models import AMBULANCE_LIFECYCLE, OPEN_TRIP, TRIP_LIFECYCLE, Ambulance, AmbulanceStatus, Trip

TRIP_STAMPS = {"enRoute": "en_route_at", "arrive": "arrived_at", "complete": "ended_at", "cancel": "ended_at"}


def _move_ambulance(ambulance: Ambulance, action: str, *, actor, reason: str = "") -> Ambulance:
    before = ambulance.status
    ambulance.status = AMBULANCE_LIFECYCLE.next(before, action)
    ambulance.status_since = timezone.now()
    ambulance.save(update_fields=["status", "status_since"])
    record(
        actor,
        "ambulance.status_changed",
        ambulance,
        before={"status": before},
        after={"status": ambulance.status},
        reason=reason or action,
    )
    return ambulance


def register_ambulance(serializer, actor) -> Ambulance:
    """Save a new ambulance at the actor's hospital (admins name the hospital) and audit-log it."""
    hospital_id = serializer.validated_data.pop("hospital_id", None)
    if actor.effective_role != Role.ADMIN or hospital_id is None:
        hospital_id = actor.hospital_id
    if hospital_id is None:
        raise PermissionDenied("Choose the hospital the ambulance is based at.")
    ambulance = serializer.save(hospital_id=hospital_id)
    record(
        actor,
        "ambulance.registered",
        ambulance,
        after={"identifier": ambulance.identifier, "type": ambulance.ambulance_type},
    )
    return ambulance


@transaction.atomic
def apply_ambulance_action(pk: int, action: str, *, actor, reason: str = "") -> Ambulance:
    """A manual status change. Another hospital's ambulance is a 404. Raises TransitionNotAllowed."""
    ambulance = get_object_or_404(Ambulance.objects.select_for_update(), pk=pk)
    if not may_change(actor, ambulance):
        raise Http404
    return _move_ambulance(ambulance, action, actor=actor, reason=reason)


def _eta(transfer: Transfer) -> int | None:
    a, b = transfer.supplier, transfer.receiver
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    return round(estimated_travel_minutes(haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)))


def _move_trip(trip: Trip, action: str, *, actor) -> Trip:
    before = trip.status
    trip.status = TRIP_LIFECYCLE.next(before, action)
    setattr(trip, TRIP_STAMPS[action], timezone.now())
    trip.save()
    record(actor, f"trip.{trip.status}", trip, before={"status": before}, after={"status": trip.status})
    return trip


@transaction.atomic
def dispatch_trip(transfer_id: int, ambulance_id: int, *, actor) -> Trip:
    """Send an available ambulance of the supplier's fleet with an approved transfer. The transfer moves to
    dispatched through its own service (which checks the actor), then the ambulance is locked and checked,
    so two dispatches can't take the same one. TransitionNotAllowed (409) if the ambulance isn't free."""
    transfer = get_object_or_404(transfers.visible_to(Transfer.objects.all(), actor), pk=transfer_id)
    transfer = transfers.dispatch(transfer, actor=actor, note="Dispatched by ambulance")
    ambulance = get_object_or_404(Ambulance.objects.select_for_update(), pk=ambulance_id)
    if actor.effective_role != Role.ADMIN and ambulance.hospital_id != transfer.supplier_id:
        raise TransitionNotAllowed("Only the supplying hospital's ambulances can carry this transfer.")
    _move_ambulance(ambulance, "startTrip", actor=actor, reason=f"Transfer #{transfer.pk}")
    trip = Trip.objects.create(ambulance=ambulance, transfer=transfer, eta_minutes=_eta(transfer))
    record(actor, "trip.dispatched", trip, after={"ambulance": ambulance.identifier, "transfer": transfer.pk})
    return trip


@transaction.atomic
def advance_trip(trip_id: int, action: str, *, actor) -> Trip:
    """Staff mark a trip en route (the transfer goes in transit) or arrived. Supplier-side rights apply."""
    trip = get_object_or_404(Trip.objects.select_for_update().select_related("transfer"), pk=trip_id)
    transfer = trip.transfer
    if not transfers.may_act(actor, transfer, "dispatch"):
        raise PermissionDenied("Only the supplying hospital tracks this trip.")
    if action == "enRoute":
        transfers.start_transit(transfer, actor=actor, note=f"{trip.ambulance.identifier} en route")
    elif action != "arrive":
        raise TransitionNotAllowed(f"Can't {action} a trip by hand.")
    return _move_trip(trip, action, actor=actor)


def end_trip_for(transfer: Transfer, *, actor) -> None:
    """The transfer was received or cancelled: complete or cancel its open trip and free the ambulance.
    Called from the transfer move, which holds the transaction."""
    try:
        trip = transfer.trip
    except ObjectDoesNotExist:
        return
    trip = Trip.objects.select_for_update().get(pk=trip.pk)
    if trip.status not in OPEN_TRIP:
        return
    _move_trip(trip, "complete" if transfer.status == "delivered" else "cancel", actor=actor)
    ambulance = Ambulance.objects.select_for_update().get(pk=trip.ambulance_id)
    if ambulance.status == AmbulanceStatus.ON_TRIP:
        _move_ambulance(
            ambulance, "endTrip", actor=actor, reason=f"Transfer #{transfer.pk} {transfer.status}"
        )
