"""Allocation (stories #45, #46): handing a held resource over to the case that holds it.

One allocation is one transaction. The resource moves to its final state (blood issued, bed occupied,
equipment or room in use), the hold becomes allocated, the need's fulfilled count goes up, the allocation is
recorded, and the case moves to where its needs now stand. If any step fails, nothing changes. Locks are taken
in the order the reservations use: case, need, hold, then resource."""

from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.permissions import can_edit, may_change
from apps.audit.services import record
from apps.emergencies.models import EmergencyRequest, RequestItem, RequestStatus, ResourceType
from apps.emergencies.services import move_case
from apps.resources.services import change_status

from .models import Allocation, Reservation, ReservationStatus
from .reservations import RESERVABLE, ReservationNotHeld, live_transfer, resource_label

# The module whose edit right lets a user allocate each type (apps.accounts.permissions.ACCESS).
ALLOCATION_MODULE = {
    ResourceType.BLOOD: "blood",
    ResourceType.BED: "beds",
    ResourceType.EQUIPMENT: "equipment",
    ResourceType.OPERATING_ROOM: "operatingRooms",
}
# The resource move that makes an allocation final, per type (see each type's lifecycle).
FINAL_ACTION = {
    ResourceType.BLOOD: "issue",
    ResourceType.BED: "admit",
    ResourceType.EQUIPMENT: "use",
    ResourceType.OPERATING_ROOM: "startCase",
}


class AllocationRefused(Exception):
    """The case can't take an allocation (closed, cancelled or fulfilled). Views answer 409, and nothing
    changes."""


def may_allocate(user, kind: str, resource) -> bool:
    """The user may allocate this type (edit on its module), and the resource is at their hospital.

    Admins may allocate at any hospital."""
    return can_edit(user.effective_role, ALLOCATION_MODULE[kind]) and may_change(user, resource)


def _not_held_message(hold: Reservation) -> str:
    if hold.status == ReservationStatus.ALLOCATED:
        return "This reservation is already allocated."
    if hold.status == ReservationStatus.HELD:
        return "This hold has run out, so it can't be allocated."
    return f"This reservation is {hold.get_status_display().lower()}, so it can't be allocated."


def _recompute_case(case: EmergencyRequest, *, now) -> None:
    """Move the case to where its needs stand, as a system move. An open case starts matching and an escalated
    one resumes it first. Fulfilled when every need is full. Otherwise partially fulfilled, and a partially
    fulfilled case stays where it is until it is complete."""
    complete = not case.items.filter(fulfilled__lt=F("quantity")).exists()
    remaining = sum(item.quantity - item.fulfilled for item in case.items.all())
    note = "Every need allocated" if complete else f"{remaining} still to allocate"
    if case.status in (RequestStatus.OPEN, RequestStatus.ESCALATED):
        start = "startMatching" if case.status == RequestStatus.OPEN else "resumeMatching"
        move_case(case, start, note=note, actor=None, at=now)
    if case.status == RequestStatus.MATCHING:
        move_case(case, "fulfil" if complete else "partiallyFulfil", note=note, actor=None, at=now)
    elif complete and case.status == RequestStatus.PARTIALLY_FULFILLED:
        move_case(case, "fulfil", note=note, actor=None, at=now)


@transaction.atomic
def allocate(reservation_id: int, *, actor, note: str = "", transfer_ok: bool = False) -> Allocation:
    """Allocate one held reservation, in one transaction. Raises PermissionDenied (403) for a role or hospital
    that can't, ReservationNotHeld (409) for a hold that is allocated, released or expired, or that belongs to
    a live transfer (unless `transfer_ok`, which only the transfer's receipt passes), AllocationRefused (409)
    for a case that is closed, cancelled or fulfilled, and TransitionNotAllowed (409) when the resource has
    moved on. Nothing is saved when any of these is raised."""
    now = timezone.now()
    case_id, item_id = Reservation.objects.values_list("request_item__request_id", "request_item_id").get(
        pk=reservation_id
    )
    case = EmergencyRequest.objects.select_for_update().get(pk=case_id)
    need = RequestItem.objects.select_for_update().get(pk=item_id)
    hold = Reservation.objects.select_for_update().select_related("hospital").get(pk=reservation_id)
    resource = hold.content_type.model_class().objects.select_for_update().get(pk=hold.object_id)

    kind = need.resource_type
    if not may_allocate(actor, kind, resource):
        raise PermissionDenied(
            "You can only allocate resources at your own hospital."
            if not may_change(actor, resource)
            else "Your role can't allocate this."
        )
    if hold.status != ReservationStatus.HELD:
        raise ReservationNotHeld(_not_held_message(hold))
    if not transfer_ok and (transfer := live_transfer(hold)):
        raise ReservationNotHeld(
            f"This hold is part of transfer #{transfer.pk}; receive the transfer instead."
        )
    if not transfer_ok and hold.expires_at <= now:
        raise ReservationNotHeld(_not_held_message(hold))
    if case.status not in RESERVABLE:
        raise AllocationRefused(f"Can't allocate for a case that is {case.get_status_display().lower()}.")

    if kind == ResourceType.BED:
        resource.admitted_at = now  # admitted with no patient recorded (see apps.hospitals.services)
    change_status(
        resource, FINAL_ACTION[kind], actor=actor, reason=f"Allocated to {case.reference}", held_ok=True
    )

    hold.status = ReservationStatus.ALLOCATED
    hold.ended_at = now
    hold.end_reason = "Allocated"
    hold.save(update_fields=["status", "ended_at", "end_reason"])

    need.fulfilled += 1
    need.save(update_fields=["fulfilled"])

    allocation = Allocation.objects.create(
        reservation=hold,
        request=case,
        request_item=need,
        hospital=hold.hospital,
        content_type=hold.content_type,
        object_id=hold.object_id,
        allocated_by=actor,
        at=now,
        note=note.strip(),
    )
    record(
        actor,
        "allocation.created",
        allocation,
        after={"resource": resource_label(resource), "fulfilled": need.fulfilled, "quantity": need.quantity},
        reason=f"For {case.reference}",
    )
    _recompute_case(case, now=now)
    return allocation


@transaction.atomic
def allocate_many(reservation_ids: list[int], *, actor) -> list[Allocation]:
    """Allocate every hold in the list in one transaction: all of them, or none.

    Holds are taken in case order, the order every other path locks cases in, so two batches can't wait on
    each other. Returns the allocations in the order asked for."""
    ids = list(dict.fromkeys(reservation_ids))
    rows = sorted(
        Reservation.objects.filter(pk__in=ids).values_list(
            "request_item__request_id", "request_item_id", "pk"
        )
    )
    if len(rows) != len(ids):
        raise Reservation.DoesNotExist("A reservation in the list doesn't exist.")
    done = {pk: allocate(pk, actor=actor) for _, _, pk in rows}
    return [done[pk] for pk in ids]
