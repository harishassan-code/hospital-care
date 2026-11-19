"""Ambulance registry (story #50) and dispatch/trip rules (story #51)."""

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
from apps.transfers.models import Transfer, TransferStatus
from apps.transfers.services import dispatch, start_transit

from .models import ACTIVE_TRIP, TRIP_LIFECYCLE, Ambulance, AmbulanceStatus, Trip, TripStatus


class TripRefused(Exception):
    """A rule the trip request breaks. Views answer 400."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


class TripConflict(Exception):
    """The move isn't allowed now. Views answer 409."""


@transaction.atomic
def apply_ambulance_action(ambulance_id: int, action: str, *, actor, reason: str = "") -> Ambulance:
    ambulance = get_object_or_404(Ambulance.objects.select_for_update(), pk=ambulance_id)
    if not may_change(actor, ambulance):
        raise Http404
    return change_status(ambulance, action, actor=actor, reason=reason)


def register_ambulance(serializer, actor) -> Ambulance:
    hospital = getattr(actor, "hospital", None)
    identifier = serializer.validated_data["identifier"]
    if Ambulance.objects.filter(hospital=hospital, identifier__iexact=identifier).exists():
        raise ValidationError({"identifier": ["This call sign is already registered in your hospital."]})
    try:
        with transaction.atomic():
            ambulance = serializer.save(hospital=hospital)
    except IntegrityError:
        raise ValidationError(
            {"identifier": ["This call sign is already registered in your hospital."]}
        ) from None
    record(
        actor,
        "ambulance.registered",
        ambulance,
        after={
            "identifier": ambulance.identifier,
            "type": ambulance.ambulance_type,
            "status": ambulance.status,
        },
    )
    return ambulance


def _may_advance_trip(user, transfer: Transfer) -> bool:
    if not can_edit(user.effective_role, "transfers"):
        return False
    if user.effective_role == Role.ADMIN:
        return True
    return user.hospital_id == transfer.supplier_id


def trip_actions_for(user, trip: Trip) -> list[str]:
    if trip.status == TripStatus.COMPLETED or not _may_advance_trip(user, trip.transfer):
        return []
    return [action for status, action in TRIP_LIFECYCLE.transitions if status == trip.status]


@transaction.atomic
def dispatch_for_transfer(transfer: Transfer, *, ambulance_id: int, actor) -> Trip:
    """Dispatch an available ambulance for an approved transfer. Moves the transfer to dispatched in the same
    transaction and marks the ambulance in use. Only one active trip per ambulance or transfer."""
    transfer = get_object_or_404(
        Transfer.objects.select_for_update().select_related("supplier", "receiver"), pk=transfer.pk
    )
    if not _may_advance_trip(actor, transfer):
        raise PermissionDenied("Your role or hospital can't dispatch this transfer.")
    if transfer.status != TransferStatus.APPROVED:
        raise TripConflict("Only an approved transfer can be dispatched with an ambulance.")
    try:
        if transfer.trip.status in ACTIVE_TRIP:
            raise TripConflict("This transfer already has an ambulance on the way.")
    except Trip.DoesNotExist:
        pass
    ambulance = get_object_or_404(Ambulance.objects.select_for_update(), pk=ambulance_id)
    if not may_change(actor, ambulance):
        raise Http404
    if ambulance.hospital_id != transfer.supplier_id:
        raise TripRefused("The ambulance must belong to the supplying hospital.", field="ambulanceId")
    if ambulance.status != AmbulanceStatus.AVAILABLE:
        raise TripConflict("Only an available ambulance can be dispatched.")
    if Trip.objects.filter(ambulance=ambulance, status__in=ACTIVE_TRIP).exists():
        raise TripConflict("This ambulance is already on a trip.")

    try:
        change_status(ambulance, "dispatch", actor=actor)
    except TransitionNotAllowed as exc:
        raise TripConflict(str(exc)) from None
    eta = None
    if transfer.supplier.latitude and transfer.receiver.latitude:
        km = hospital_distance(transfer.supplier, transfer.receiver)
        eta = round(estimated_travel_minutes(km))

    trip = Trip.objects.create(
        transfer=transfer,
        ambulance=ambulance,
        status=TripStatus.DISPATCHED,
        eta_minutes=eta,
        dispatched_by=actor,
    )
    record(
        actor,
        "trip.dispatched",
        trip,
        after={"transferId": transfer.pk, "ambulance": ambulance.identifier, "status": trip.status},
    )
    dispatch(transfer, actor=actor, note=f"Ambulance {ambulance.identifier}")
    return trip


@transaction.atomic
def advance_trip(trip_id: int, action: str, *, actor) -> Trip:
    trip = get_object_or_404(
        Trip.objects.select_for_update().select_related("transfer", "ambulance__hospital"), pk=trip_id
    )
    transfer = Transfer.objects.select_for_update().get(pk=trip.transfer_id)
    ambulance = Ambulance.objects.select_for_update().get(pk=trip.ambulance_id)
    if not _may_advance_trip(actor, transfer):
        raise PermissionDenied("Your role or hospital can't update this trip.")
    try:
        TRIP_LIFECYCLE.next(trip.status, action)
    except TransitionNotAllowed as exc:
        raise TripConflict(str(exc)) from None

    before = trip.status
    trip.status = TRIP_LIFECYCLE.next(before, action)
    trip.status_since = timezone.now()
    trip.save(update_fields=["status", "status_since"])
    record(
        actor,
        f"trip.{trip.status}",
        trip,
        before={"status": before},
        after={"status": trip.status},
        reason=action,
    )

    if action == "arrive" and transfer.status == TransferStatus.DISPATCHED:
        start_transit(transfer, actor=actor, note=f"Ambulance {ambulance.identifier} arrived")
    elif action == "complete":
        try:
            change_status(ambulance, "release", actor=actor)
        except TransitionNotAllowed as exc:
            raise TripConflict(str(exc)) from None
    return trip
