"""Atomic resource reservation (stories #43, #44): holding a matched resource for one need of one emergency
case.

A hold moves its resource to the reserved status through change_status, and every search for stock looks
for an available or free status, so a held resource drops out of all of them. The database makes sure no
resource has two active holds (Reservation's partial unique constraint). Locking keeps the rules in order:
reserving takes the case, then the need, then the resources it picks, skipping any that another transaction
holds."""

from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.utils import timezone

from apps.audit.services import record
from apps.blood.models import BloodUnit, Component
from apps.emergencies.models import EmergencyRequest, RequestItem, RequestStatus, ResourceType
from apps.emergencies.services import move_case
from apps.equipment.models import Equipment
from apps.hospitals.models import Bed
from apps.operating_rooms.models import OperatingRoom
from apps.resources.services import change_status
from apps.resources.state_machine import TransitionNotAllowed

from .candidates import REGISTRY
from .models import ACTIVE, Reservation, ReservationStatus

HOLD_ACTION = "reserve"
RELEASE_ACTION = "cancelReservation"
# The statuses a case can still take stock for. Fulfilled, closed and cancelled cases can't.
RESERVABLE = (
    RequestStatus.OPEN,
    RequestStatus.MATCHING,
    RequestStatus.PARTIALLY_FULFILLED,
    RequestStatus.ESCALATED,
)


class ReservationUnavailable(Exception):
    """Nothing could be reserved: no free resource at the hospital, too many asked for, or the case can't take
    stock. Views answer 400, and nothing is changed."""


class ReservationNotHeld(Exception):
    """The reservation is no longer held, so it can't be released. Views answer 409."""


def resource_label(resource) -> str:
    """The resource as staff name it: "O- red cells DN-0042", "Bed ICU-03", "Ventilator VENT-003", "OR 1"."""
    if isinstance(resource, BloodUnit):
        return f"{resource.group} {Component(resource.component).label.lower()} {resource.donation_number}"
    if isinstance(resource, Bed):
        return f"Bed {resource.label}"
    if isinstance(resource, Equipment):
        return f"{resource.get_equipment_type_display()} {resource.identifier}"
    if isinstance(resource, OperatingRoom):
        return resource.name
    return str(resource)


def active_holds(item: RequestItem) -> int:
    """How many of the need's resources are held right now. An allocated hold is already in the need's
    fulfilled count, so it is not counted again (story #45)."""
    return item.reservations.filter(status=ReservationStatus.HELD).count()


def _free_resources(item: RequestItem, hospital, limit: int) -> list:
    """Up to `limit` resources the registry allows for the need, at this hospital, locked, skipping any
    another transaction holds. A resource with an active hold is never picked, even if its status still
    says free."""
    matchable = REGISTRY[item.resource_type](item).filter(hospital=hospital)
    if item.resource_type != ResourceType.BLOOD:
        matchable = matchable.order_by("id")  # blood keeps the donor-rank order from compatible_units
    held = Reservation.objects.filter(
        content_type=ContentType.objects.get_for_model(matchable.model),
        object_id=OuterRef("pk"),
        status__in=ACTIVE,
    )
    return list(matchable.filter(~Exists(held)).select_for_update(skip_locked=True)[:limit])


@transaction.atomic
def reserve(item: RequestItem, *, hospital, quantity: int, actor) -> list[Reservation]:
    """Hold up to `quantity` resources for one need, at the case's own hospital (or any hospital, for the
    transfer story). Returns the holds made, which can be fewer than asked when the hospital has fewer free.
    Raises ReservationUnavailable, and changes nothing, when nothing is free or the need can't take that many
    more.

    The case and the need are locked first, so two reservations for one case take turns. Resources are locked
    with skip_locked, so a concurrent reserver skips a unit it can't get and takes the next one, never waits
    on it. The hold lasts RESERVATION_HOLD_MINUTES. An open case moves to matching as a system move."""
    if hospital is None:
        raise ReservationUnavailable("This case has no hospital, so there is no local stock to reserve.")
    case = EmergencyRequest.objects.select_for_update().get(pk=item.request_id)
    need = RequestItem.objects.select_for_update().get(pk=item.pk)
    if case.status not in RESERVABLE:
        raise ReservationUnavailable(
            f"Can't reserve stock for a case that is {case.get_status_display().lower()}."
        )

    remaining = need.quantity - need.fulfilled - active_holds(need)
    if quantity > remaining:
        raise ReservationUnavailable(f"Only {max(remaining, 0)} more can be reserved for this need.")

    found = _free_resources(need, hospital, quantity)
    if not found:
        raise ReservationUnavailable("No matching stock is free at this hospital.")

    now = timezone.now()
    expires_at = now + timedelta(minutes=settings.RESERVATION_HOLD_MINUTES)
    reservations = []
    for resource in found:
        change_status(
            resource, HOLD_ACTION, actor=actor, reason=f"Reserved for {case.reference}", held_ok=True
        )
        reservation = Reservation.objects.create(
            request_item=need,
            resource=resource,
            hospital=hospital,
            reserved_by=actor,
            expires_at=expires_at,
        )
        record(
            actor,
            "reservation.created",
            reservation,
            after={
                "resource": resource_label(resource),
                "status": reservation.status,
                "expiresAt": expires_at.isoformat(),
            },
            reason=f"For {case.reference}",
        )
        reservations.append(reservation)

    if case.status == RequestStatus.OPEN:
        move_case(case, "startMatching", note=f"Stock reserved at {hospital.name}", actor=None, at=now)
    return reservations


def _end(hold: Reservation, *, status: str, actor, reason: str, now) -> Reservation:
    """Free the hold's resource and end the hold. The caller holds the case, the hold and the transaction. If
    the resource has already moved on (issued, expired, out of service), the hold ends and the resource is
    left alone."""
    resource = hold.content_type.model_class().objects.select_for_update().filter(pk=hold.object_id).first()
    if resource is not None:
        try:
            resource.machine.next(resource.status, RELEASE_ACTION)
        except TransitionNotAllowed:
            pass  # the resource has moved on: nothing to free
        else:
            change_status(resource, RELEASE_ACTION, actor=actor, reason=reason, held_ok=True)
    hold.status = status
    hold.ended_at = now
    hold.end_reason = reason
    hold.save(update_fields=["status", "ended_at", "end_reason"])
    record(
        actor,
        f"reservation.{status}",
        hold,
        before={"status": ReservationStatus.HELD},
        after={"status": status},
        reason=reason,
    )
    return hold


@transaction.atomic
def release(reservation: Reservation, *, actor, reason: str) -> Reservation:
    """Release a held reservation: its resource goes back to available or free. Raises ReservationNotHeld, and
    changes nothing, when the hold is already allocated, released or expired. Locks the case, then the
    hold."""
    case_id = RequestItem.objects.values_list("request_id", flat=True).get(pk=reservation.request_item_id)
    EmergencyRequest.objects.select_for_update().get(pk=case_id)
    hold = Reservation.objects.select_for_update().get(pk=reservation.pk)
    if hold.status != ReservationStatus.HELD:
        raise ReservationNotHeld(
            f"This reservation is {hold.get_status_display().lower()}, so it can't be released."
        )
    return _end(hold, status=ReservationStatus.RELEASED, actor=actor, reason=reason, now=timezone.now())


def release_expired(now=None) -> int:
    """Release every held reservation whose hold has run out, and return how many. Runs as the system (no
    actor). Each hold is locked with skip_locked and checked again under the lock, so two runs, or a run
    and a release, never end the same hold twice. Idempotent: an expired hold is no longer held.

    ponytail: a request-time sweep (the case list, case and candidates GETs and the reservation endpoints
    call it). Ceiling: read traffic or hold volume grows; then run `release_expired_reservations` on a
    scheduler and drop the calls from the views."""
    now = now or timezone.now()
    due = list(
        Reservation.objects.filter(status=ReservationStatus.HELD, expires_at__lte=now).values_list(
            "pk", flat=True
        )
    )
    released = 0
    for pk in due:
        with transaction.atomic():
            hold = (
                Reservation.objects.select_for_update(skip_locked=True)
                .filter(pk=pk, status=ReservationStatus.HELD, expires_at__lte=now)
                .first()
            )
            if hold is None:
                continue
            _end(hold, status=ReservationStatus.EXPIRED, actor=None, reason="Hold expired", now=now)
            released += 1
    return released
