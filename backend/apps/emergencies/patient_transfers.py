"""Patient transfers (B17, stories #63 to #65): moving a case's patient to another hospital, and the hospital
that receives the patient confirming arrival.

The sending hospital asks for the move to one of the hospitals in the case's #42 list, and can cancel it while
it is requested. Arrival is the receiving hospital's confirmation: in one transaction the case becomes theirs,
the holds the sending hospital still has on the case are released, and the case's requested stock transfers
are cancelled. Views only translate the exceptions below into status codes.

Lock order, in every write: the case, then the patient transfer, then the case's held reservations, then its
stock transfers, then the resources (taken inside `release`). Every path that touches a case locks the case
first, so two moves on one case take turns."""

from django.db import transaction
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.accounts.permissions import can_edit, may_change
from apps.audit.services import record
from apps.core import clock
from apps.hospitals.models import Hospital
from apps.matching.candidates import candidates_for_case
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.multi import match_hospitals
from apps.matching.reservations import RESERVABLE, release
from apps.resources.state_machine import TransitionNotAllowed

from .availability import local_availability
from .labels import hospital_match_data
from .models import (
    PATIENT_TRANSFER_LIFECYCLE,
    EmergencyRequest,
    PatientTransfer,
    PatientTransferStatus,
    Severity,
)

PT = PatientTransferStatus

# The message when the actor may not make the move (403). Visibility is decided before this (404).
ACTOR_MESSAGE = {
    "arrive": "Only staff at the receiving hospital who may edit emergencies can confirm arrival.",
    "cancel": "Only staff at the sending hospital who may edit emergencies can cancel the transfer.",
}


class PatientTransferRefused(Exception):
    """The request breaks a rule. Views answer 400 with {field: [message]}, or {"detail": message} when no
    field is named. Nothing is saved."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


class PatientTransferConflict(Exception):
    """The move isn't allowed now: the lifecycle refuses it, the case already has a transfer on its way, or
    stock for the case is still under way. Views answer 409, and nothing is saved."""


# ── Who sees, who may act, and what a case shows ──────────────────────────────────────────────────


def visible_to(queryset, user):
    """The patient transfers the user may see: those where their hospital is the sending or the receiving one.
    Admins see all of them. A user with no hospital sees none."""
    if user.effective_role == Role.ADMIN:
        return queryset
    if user.hospital_id is None:
        return queryset.none()
    return queryset.filter(Q(from_hospital_id=user.hospital_id) | Q(to_hospital_id=user.hospital_id))


def in_direction(queryset, user, direction: str | None):
    """Incoming: the user's hospital is the receiving one. Outgoing: the sending one. With no hospital (an
    admin) there is no side, so the direction is ignored."""
    if direction is None or user.hospital_id is None:
        return queryset
    if direction == "incoming":
        return queryset.filter(to_hospital_id=user.hospital_id)
    return queryset.filter(from_hospital_id=user.hospital_id)


def may_act(user, transfer: PatientTransfer, action: str) -> bool:
    """Whether the user may make this move now, ignoring the lifecycle. Both moves need edit on emergencies:
    arrival at the receiving hospital, cancellation at the sending one. Admins may make either."""
    if not can_edit(user.effective_role, "emergencies"):
        return False
    if user.effective_role == Role.ADMIN:
        return True
    if action == "arrive":
        return user.hospital_id == transfer.to_hospital_id
    if action == "cancel":
        return user.hospital_id == transfer.from_hospital_id
    return False


def actions_for(user, transfer: PatientTransfer) -> list[str]:
    """The moves the user may make on this transfer now: valid from its status and allowed to the user."""
    return [
        action
        for status, action in PATIENT_TRANSFER_LIFECYCLE.transitions
        if status == transfer.status and may_act(user, transfer, action)
    ]


def transfer_flag(case: EmergencyRequest, rows=None) -> bool:
    """Whether the case may need a transfer (story #63): it is critical, and at least one need is short here
    after the holds it has (#33, #43). Worked out on read, never stored. `rows` is the case's local
    availability when the caller has it already."""
    if case.severity != Severity.CRITICAL:
        return False
    rows = local_availability(case) if rows is None else rows
    return any(row.shortfall > 0 for row in rows)


# ── Locks and the one place a transfer's status changes ───────────────────────────────────────────


def _begin(transfer: PatientTransfer, action: str, *, actor) -> PatientTransfer:
    """The start of every move: lock the case, then the transfer. Refuses with PermissionDenied (403) when the
    user may not make the move, and with PatientTransferConflict (409) when the lifecycle doesn't allow it
    from the current status. Returns the locked transfer."""
    case_id = PatientTransfer.objects.values_list("request_id", flat=True).get(pk=transfer.pk)
    EmergencyRequest.objects.select_for_update().get(pk=case_id)
    locked = PatientTransfer.objects.select_for_update().get(pk=transfer.pk)
    if not may_act(actor, locked, action):
        raise PermissionDenied(ACTOR_MESSAGE[action])
    try:
        PATIENT_TRANSFER_LIFECYCLE.next(locked.status, action)
    except TransitionNotAllowed as exc:
        raise PatientTransferConflict(str(exc)) from None
    return locked


def _move(transfer: PatientTransfer, action: str, *, actor, audit_reason: str, **fields) -> PatientTransfer:
    """The one place a transfer's status changes: the move, the fields it sets and its audit record. The
    caller holds the locks and the transaction, and has checked the move with `_begin`."""
    before = transfer.status
    transfer.status = PATIENT_TRANSFER_LIFECYCLE.next(before, action)
    for name, value in fields.items():
        setattr(transfer, name, value)
    transfer.save(update_fields=["status", *fields])
    record(
        actor,
        f"patienttransfer.{transfer.status}",
        transfer,
        before={"status": before},
        after={"status": transfer.status},
        reason=audit_reason,
    )
    return transfer


# ── Requesting (story #64) ────────────────────────────────────────────────────────────────────────


@transaction.atomic
def request_patient_transfer(
    case: EmergencyRequest, *, destination: Hospital, note: str = "", actor
) -> PatientTransfer:
    """Ask to move the case's patient to `destination`, which must be one of the hospitals in the case's #42
    list. The row keeps that hospital's match as it stands now. Nothing is reserved at the destination.

    Refused with PatientTransferRefused (400), and nothing saved, when the case has no hospital, nothing is
    short, the case can't take stock, the destination is the case's own or inactive, or it isn't in the list.
    A second open transfer for the case is PatientTransferConflict (409). PermissionDenied (403) unless the
    user may edit emergencies at the case's hospital (admins: any). The case is locked first, so two requests
    take turns."""
    locked = EmergencyRequest.objects.select_for_update().get(pk=case.pk)
    if not (can_edit(actor.effective_role, "emergencies") and may_change(actor, locked)):
        raise PermissionDenied(
            "Only staff at the case's hospital who may edit emergencies can move a patient."
        )
    if PatientTransfer.objects.filter(request=locked, status=PT.REQUESTED).exists():
        raise PatientTransferConflict("This case already has a patient transfer on its way. Cancel it first.")
    if locked.hospital_id is None:
        raise PatientTransferRefused("This case has no hospital, so a patient can't be moved from it.")
    if locked.status not in RESERVABLE:
        raise PatientTransferRefused(
            f"Can't move a patient for a case that is {locked.get_status_display().lower()}."
        )
    found = candidates_for_case(locked)
    if not found:
        raise PatientTransferRefused("Nothing is short here, so the patient doesn't need to move.")
    if destination.pk == locked.hospital_id:
        raise PatientTransferRefused(
            "The case's own hospital can't be the destination.", field="destinationId"
        )
    if not destination.is_active:
        raise PatientTransferRefused(
            "That hospital is not active, so it can't receive a patient.", field="destinationId"
        )
    match = next((m for m in match_hospitals(found) if m.hospital.pk == destination.pk), None)
    if match is None:
        raise PatientTransferRefused(
            "That hospital isn't one of the hospitals that can cover this case.", field="destinationId"
        )

    transfer = PatientTransfer.objects.create(
        request=locked,
        from_hospital_id=locked.hospital_id,
        to_hospital=destination,
        match=hospital_match_data(match),
        note=note.strip(),
        requested_by=actor,
    )
    record(
        actor,
        "patienttransfer.requested",
        transfer,
        after={"status": transfer.status, "to": {"id": destination.pk, "name": destination.name}},
        reason=f"For {locked.reference}",
    )
    return transfer


# ── Arrival (story #65) ───────────────────────────────────────────────────────────────────────────


@transaction.atomic
def arrive_patient(transfer: PatientTransfer, *, actor) -> PatientTransfer:
    """The receiving hospital confirms the patient has arrived. In one transaction: the case moves to the
    destination, the holds the sending hospital still has on the case are released (allocated ones stay), the
    case's requested stock transfers are cancelled, and the transfer is arrived with who and when.

    Refused with PatientTransferConflict (409), and nothing changed, when the transfer is no longer requested
    or when stock transfers for the case are approved, dispatched or in transit (they are named). Destination
    stock isn't checked: the patient is already on the way. PermissionDenied (403) unless the user may edit
    emergencies at the destination (admins: any)."""
    from apps.transfers.services import (
        cancel_requested_for_case,
        live_transfers_of_case,
    )  # transfers build on this

    locked = _begin(transfer, "arrive", actor=actor)
    case = EmergencyRequest.objects.get(pk=locked.request_id)
    holds = list(
        Reservation.objects.select_for_update()
        .filter(request_item__request=case, status=ReservationStatus.HELD)
        .order_by("created_at", "id")
    )
    live = live_transfers_of_case(case)
    if live:
        named = ", ".join(f"#{stock.pk} ({stock.get_status_display().lower()})" for stock in live)
        raise PatientTransferConflict(
            f"Stock for this case is still on its way: transfer {named}. "
            "Finish or cancel it before the patient arrives."
        )
    reason = f"Patient arrived at {locked.to_hospital.name}"
    cancel_requested_for_case(case, actor=actor, reason=reason)
    for hold in holds:
        hold.refresh_from_db()
        if hold.status == ReservationStatus.HELD:
            release(hold, actor=actor, reason=reason)

    sending = locked.from_hospital
    receiving = locked.to_hospital
    case.hospital = receiving
    case.save(update_fields=["hospital"])
    record(
        actor,
        "emergencyrequest.hospital_changed",
        case,
        before={"hospital": {"id": sending.pk, "name": sending.name}},
        after={"hospital": {"id": receiving.pk, "name": receiving.name}},
        reason=f"Patient transfer #{locked.pk}",
    )
    return _move(
        locked,
        "arrive",
        actor=actor,
        audit_reason=f"From {sending.name}",
        arrived_by=actor,
        arrived_at=clock.now(),
    )


# ── Cancelling (story #65, cancel) ────────────────────────────────────────────────────────────────


@transaction.atomic
def cancel_patient_transfer(transfer: PatientTransfer, *, actor, reason: str) -> PatientTransfer:
    """The sending hospital cancels a requested transfer, with a reason. The case stays where it is, and its
    holds and stock transfers are left alone.

    Refused with PatientTransferRefused (400) when the reason is blank, and PatientTransferConflict (409) when
    the transfer is no longer requested. PermissionDenied (403) unless the user may edit emergencies at the
    sending hospital (admins: any)."""
    locked = _begin(transfer, "cancel", actor=actor)
    reason = reason.strip()
    if not reason:
        raise PatientTransferRefused("Say why the transfer is cancelled.", field="reason")
    return _move(locked, "cancel", actor=actor, audit_reason=reason, reason=reason)


@transaction.atomic
def cancel_open_patient_transfer(case: EmergencyRequest, *, actor, reason: str) -> int:
    """Cancel the case's requested transfer, if it has one, when the case is closed or cancelled. Called from
    the case move in the same transaction, so no arrival can follow a closed case. The case move has already
    checked the actor, so there is no per-user check. The caller holds the case lock. Returns how many it
    cancelled."""
    open_transfers = list(
        PatientTransfer.objects.select_for_update().filter(request=case, status=PT.REQUESTED)
    )
    for transfer in open_transfers:
        _move(transfer, "cancel", actor=actor, audit_reason=reason, reason=reason)
    return len(open_transfers)
