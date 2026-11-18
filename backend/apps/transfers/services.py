"""Inter-hospital transfer rules (stories #47, #48, #49). Every move is one transaction that locks the
case, the need, the transfer, then its holds and resources (the order reservation and allocation use),
writes one history entry and one audit record. Views only translate the exceptions below into status codes."""

from django.db import transaction
from django.db.models import Q, Sum
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.accounts.permissions import can_edit, may_change
from apps.audit.services import record
from apps.emergencies.models import EmergencyRequest, RequestItem, ResourceType
from apps.hospitals.models import Hospital
from apps.matching.allocations import ALLOCATION_MODULE, AllocationRefused, allocate
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.reservations import (
    RESERVABLE,
    ReservationNotHeld,
    ReservationUnavailable,
    active_holds,
    release,
    reserve,
)
from apps.resources.state_machine import TransitionNotAllowed

from .models import LIVE, TRANSFER_LIFECYCLE, Transfer, TransferStatus, TransferStatusChange

# Only stock that physically moves between hospitals. Beds and operating rooms are patient transfer (#63 to
# #65).
TRANSFERABLE = (ResourceType.BLOOD, ResourceType.EQUIPMENT)
# The moves the supplier's staff make. The requester makes cancel and deliver.
SUPPLIER_MOVES = ("approve", "reject", "dispatch", "startTransit")


class TransferRefused(Exception):
    """The request breaks a rule. Views answer 400 with {field: [message]}, or {"detail": message} when no
    field is named. Nothing is saved."""

    def __init__(self, message: str, field: str | None = None):
        super().__init__(message)
        self.field = field


class TransferConflict(Exception):
    """The move isn't allowed now: the lifecycle refuses it, the stock is no longer free, or the case or a
    hold has moved on. Views answer 409, and nothing is saved."""


# ── Who sees and who may act ──────────────────────────────────────────────────────────────────────


def visible_to(queryset, user):
    """The transfers the user may see: those where their hospital is the supplier or the receiver. Admins see
    the whole network. A user with no hospital sees none."""
    if user.effective_role == Role.ADMIN:
        return queryset
    if user.hospital_id is None:
        return queryset.none()
    return queryset.filter(Q(supplier_id=user.hospital_id) | Q(receiver_id=user.hospital_id))


def in_direction(queryset, user, direction: str | None):
    """Incoming: the user's hospital is the supplier (it was asked). Outgoing: the receiver (it asked).
    With no hospital (an admin) there is no side, so the direction is ignored."""
    if direction is None or user.hospital_id is None:
        return queryset
    if direction == "incoming":
        return queryset.filter(supplier_id=user.hospital_id)
    return queryset.filter(receiver_id=user.hospital_id)


def may_act(user, transfer: Transfer, action: str) -> bool:
    """Whether the user may make this move now, ignoring the lifecycle. Supplier moves need edit on the
    resource's module at the supplying hospital; cancel needs edit on emergencies at the receiving
    hospital; receipt needs edit on the module at the receiving hospital. Admins may make any move."""
    role = user.effective_role
    admin = role == Role.ADMIN
    module = ALLOCATION_MODULE[transfer.request_item.resource_type]
    if action in SUPPLIER_MOVES:
        return can_edit(role, module) and (admin or user.hospital_id == transfer.supplier_id)
    if action == "deliver":
        return can_edit(role, module) and (admin or user.hospital_id == transfer.receiver_id)
    if action == "cancel":
        return can_edit(role, "emergencies") and (admin or user.hospital_id == transfer.receiver_id)
    return False


def actions_for(user, transfer: Transfer) -> list[str]:
    """The moves the user may make on this transfer now: valid from its status and allowed to the user."""
    return [
        action
        for status, action in TRANSFER_LIFECYCLE.transitions
        if status == transfer.status and may_act(user, transfer, action)
    ]


# ── Locks, checks and the one place a status changes ──────────────────────────────────────────────


def _lock(transfer: Transfer) -> Transfer:
    """Lock the case, the need, then the transfer, and return the transfer as it now is."""
    case_id, item_id = Transfer.objects.values_list("request_item__request_id", "request_item_id").get(
        pk=transfer.pk
    )
    EmergencyRequest.objects.select_for_update().get(pk=case_id)
    RequestItem.objects.select_for_update().get(pk=item_id)
    return Transfer.objects.select_for_update().get(pk=transfer.pk)


def _begin(transfer: Transfer, action: str, *, actor) -> Transfer:
    """The start of every move: lock the rows, then refuse with 403 if the user may not make the move, or with
    409 if the lifecycle doesn't allow it from the current status. Returns the locked transfer."""
    locked = _lock(transfer)
    if not may_act(actor, locked, action):
        raise PermissionDenied("Your role or hospital can't make this move.")
    try:
        TRANSFER_LIFECYCLE.next(locked.status, action)
    except TransitionNotAllowed as exc:
        raise TransferConflict(str(exc)) from None
    return locked


def _holds(transfer: Transfer) -> list[Reservation]:
    """The transfer's holds, locked, in the order they were made."""
    return list(
        Reservation.objects.select_for_update().filter(transfers=transfer).order_by("created_at", "id")
    )


def _move(transfer: Transfer, action: str, *, actor, note: str = "", reason: str | None = None) -> Transfer:
    """The one place a transfer's status changes: the move, its history entry and its audit record. The caller
    holds the locks and the transaction, and has checked the move with `_begin`."""
    before = transfer.status
    transfer.status = TRANSFER_LIFECYCLE.next(before, action)
    fields = ["status"]
    if reason is not None:
        transfer.reason = reason
        fields.append("reason")
    transfer.save(update_fields=fields)
    TransferStatusChange.objects.create(
        transfer=transfer,
        from_status=before,
        to_status=transfer.status,
        action=action,
        note=note,
        actor=actor,
    )
    record(
        actor,
        f"transfer.{transfer.status}",
        transfer,
        before={"status": before},
        after={"status": transfer.status},
        reason=note or action,
    )
    return transfer


# ── Requesting (story #47) ────────────────────────────────────────────────────────────────────────


@transaction.atomic
def request_transfer(
    item: RequestItem, *, supplier: Hospital, quantity: int, actor, note: str = ""
) -> Transfer:
    """Ask `supplier` for `quantity` of one need of the case. Nothing is reserved yet, so the supplier's
    stock stays free until it answers. Refused with TransferRefused (400) when the supplier is the case's
    own hospital, the need is a bed or an operating room, the case can't take stock, or the quantity is
    more than the need has left after its fulfilled units, its holds and the requests still waiting for an
    answer. PermissionDenied (403) unless the user may edit emergencies at the case's hospital (admins:
    any). Locks the case, then the need."""
    case = EmergencyRequest.objects.select_for_update().get(pk=item.request_id)
    need = RequestItem.objects.select_for_update().get(pk=item.pk)
    if not (can_edit(actor.effective_role, "emergencies") and may_change(actor, case)):
        raise PermissionDenied(
            "Only staff at the case's hospital who may edit emergencies can ask for transfers."
        )
    if case.hospital_id is None:
        raise TransferRefused("This case has no hospital, so nothing can be sent to it.")
    if supplier.pk == case.hospital_id:
        raise TransferRefused("The case's own hospital can't be the supplier.", field="supplierId")
    if need.resource_type not in TRANSFERABLE:
        raise TransferRefused("Only blood and equipment can be transferred.", field="itemId")
    if case.status not in RESERVABLE:
        raise TransferRefused(f"Can't ask for stock for a case that is {case.get_status_display().lower()}.")
    waiting = need.transfers.filter(status=TransferStatus.REQUESTED).aggregate(total=Sum("quantity"))["total"]
    free = need.quantity - need.fulfilled - active_holds(need) - (waiting or 0)
    if quantity > free:
        raise TransferRefused(f"Only {max(free, 0)} more can be asked for this need.", field="quantity")

    transfer = Transfer.objects.create(
        request_item=need,
        supplier=supplier,
        receiver_id=case.hospital_id,
        quantity=quantity,
        requested_by=actor,
    )
    TransferStatusChange.objects.create(
        transfer=transfer, from_status="", to_status=transfer.status, action="request", note=note, actor=actor
    )
    record(
        actor,
        "transfer.requested",
        transfer,
        after={"status": transfer.status, "quantity": quantity},
        reason=f"For {case.reference}",
    )
    return transfer


# ── Answering and tracking (stories #47, #48) ─────────────────────────────────────────────────────


@transaction.atomic
def approve(transfer: Transfer, *, actor, note: str = "") -> Transfer:
    """The supplier approves a requested transfer: `reserve` holds the units at the supplier, in this
    transaction, and the holds are linked to the transfer, which pins them. If fewer are free than asked,
    what is free is held (partial approval). If none is free, or the case can't take stock,
    TransferConflict (409) and the transfer stays requested."""
    transfer = _begin(transfer, "approve", actor=actor)
    try:
        holds = reserve(
            transfer.request_item, hospital=transfer.supplier, quantity=transfer.quantity, actor=actor
        )
    except ReservationUnavailable as exc:
        raise TransferConflict(str(exc)) from None
    transfer.reservations.add(*holds)
    return _move(transfer, "approve", actor=actor, note=note)


@transaction.atomic
def reject(transfer: Transfer, *, actor, reason: str, note: str = "") -> Transfer:
    """The supplier refuses a requested transfer. A reason is required (TransferRefused, field "reason").
    Reserves nothing."""
    transfer = _begin(transfer, "reject", actor=actor)
    reason = reason.strip()
    if not reason:
        raise TransferRefused("Say why the request is rejected.", field="reason")
    return _move(transfer, "reject", actor=actor, note=note or reason, reason=reason)


@transaction.atomic
def cancel(transfer: Transfer, *, actor, reason: str = "", note: str = "") -> Transfer:
    """The requester cancels a transfer that isn't finished: requested, approved, dispatched or in transit.
    Each hold it still has is released in the same transaction, so the units count as the supplier's stock
    again, even after dispatch (what was sent comes back)."""
    transfer = _begin(transfer, "cancel", actor=actor)
    reason = reason.strip()
    for hold in _holds(transfer):
        if hold.status == ReservationStatus.HELD:
            release(hold, actor=actor, reason=f"Transfer #{transfer.pk} cancelled", transfer_ok=True)
    return _move(transfer, "cancel", actor=actor, note=note or reason, reason=reason)


@transaction.atomic
def cancel_for_case(case: EmergencyRequest, *, actor, reason: str) -> int:
    """Cancel every unfinished transfer of a case that is being closed or cancelled, releasing its holds, and
    return how many. Called from the case move, which has already checked the actor, so no per-transfer
    check: without this, a closed case's pinned holds would never expire and the supplier's stock would stay
    locked. The caller holds the case lock and the transaction."""
    unfinished = Transfer.objects.select_for_update().filter(
        request_item__request=case, status__in=(TransferStatus.REQUESTED, *LIVE)
    )
    cancelled = 0
    for transfer in unfinished.order_by("id"):
        for hold in _holds(transfer):
            if hold.status == ReservationStatus.HELD:
                release(hold, actor=actor, reason=f"Transfer #{transfer.pk} cancelled", transfer_ok=True)
        _move(transfer, "cancel", actor=actor, note=reason, reason=reason)
        cancelled += 1
    return cancelled


@transaction.atomic
def dispatch(transfer: Transfer, *, actor, note: str = "") -> Transfer:
    """The supplier sends an approved transfer on its way. Its holds stay pinned."""
    transfer = _begin(transfer, "dispatch", actor=actor)
    return _move(transfer, "dispatch", actor=actor, note=note)


@transaction.atomic
def start_transit(transfer: Transfer, *, actor, note: str = "") -> Transfer:
    """The stock is on the road: a dispatched transfer goes in transit."""
    transfer = _begin(transfer, "startTransit", actor=actor)
    return _move(transfer, "startTransit", actor=actor, note=note)


# ── Receipt (story #49) ───────────────────────────────────────────────────────────────────────────


def _move_to_receiver(hold: Reservation, transfer: Transfer, *, actor) -> None:
    """Put one held unit on the receiver's books: its hospital becomes the receiver, its storage place is
    cleared and its location says where it came from. Its status moves in `allocate`, next."""
    resource = hold.content_type.model_class().objects.select_for_update().get(pk=hold.object_id)
    supplier, receiver = transfer.supplier, transfer.receiver
    resource.hospital = receiver
    resource.storage_location = None
    limit = resource._meta.get_field("location").max_length
    resource.location = f"Received from {supplier.name}"[:limit]
    resource.save(update_fields=["hospital", "storage_location", "location"])
    record(
        actor,
        f"{resource._meta.model_name}.transferred",
        resource,
        before={"hospital": {"id": supplier.pk, "name": supplier.name}},
        after={"hospital": {"id": receiver.pk, "name": receiver.name}},
        reason=f"Transfer #{transfer.pk}",
    )


@transaction.atomic
def receive(transfer: Transfer, *, actor, note: str = "") -> Transfer:
    """The receiving hospital confirms a dispatched or in-transit transfer. In this one transaction, for
    each held unit: it moves to the receiver, then `allocate` puts it to the case (blood issued, equipment
    in use, the allocation recorded, the case recomputed), and finally the transfer is delivered. If any
    step is refused (a unit that expired on the way, a closed case), TransferConflict (409) and every unit
    is put back."""
    transfer = _begin(transfer, "deliver", actor=actor)
    try:
        for hold in _holds(transfer):
            _move_to_receiver(hold, transfer, actor=actor)
            allocate(hold.pk, actor=actor, note=note, transfer_ok=True)
    except (TransitionNotAllowed, AllocationRefused, ReservationNotHeld) as exc:
        raise TransferConflict(str(exc)) from None
    return _move(transfer, "deliver", actor=actor, note=note)
