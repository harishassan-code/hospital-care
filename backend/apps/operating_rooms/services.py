"""Operating room registry (story #28) and bookings (story #29): registering rooms, changing their status,
booking a time slot in a room, cancelling it, and the day schedule."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import Role
from apps.accounts.permissions import may_change
from apps.audit.services import record
from apps.resources.services import change_status
from apps.resources.state_machine import TransitionNotAllowed

from .models import OperatingRoom, OrBooking, OrBookingStatus, OrStatus
from .serializers import OrBookingSerializer

DUPLICATE_NAME = {"name": ["A room with this name is already registered in your hospital."]}


def register_operating_room(serializer, actor) -> OperatingRoom:
    """Save a new room in the actor's hospital and audit-log it. Names are unique per hospital, any case."""
    hospital = getattr(actor, "hospital", None)
    name = serializer.validated_data["name"]
    if OperatingRoom.objects.filter(hospital=hospital, name__iexact=name).exists():
        raise ValidationError(DUPLICATE_NAME)
    try:
        with transaction.atomic():
            room = serializer.save(hospital=hospital)
    except IntegrityError:  # someone registered the same name at the same moment
        raise ValidationError(DUPLICATE_NAME) from None
    record(
        actor,
        "operatingroom.registered",
        room,
        after={"name": room.name, "capabilities": room.capabilities, "status": room.status},
    )
    return room


@transaction.atomic
def apply_operating_room_action(room_id: int, action: str, *, actor, reason: str = "") -> OperatingRoom:
    """Move a room along its lifecycle, locking the row. Another hospital's room is a 404 (own-hospital
    rule, may_change), so its existence isn't revealed. Raises TransitionNotAllowed for a refused move."""
    room = get_object_or_404(OperatingRoom.objects.select_for_update(), pk=room_id)
    if not may_change(actor, room):
        raise Http404
    return change_status(room, action, actor=actor, reason=reason)


# ── Bookings (story #29) ──────────────────────────────────────────────────────────────────────────


def _clash(room: OperatingRoom, starts_at: datetime, ends_at: datetime):
    """The booked slot in this room that overlaps [starts_at, ends_at), if any. Half-open, so a slot that ends
    when the next begins doesn't clash."""
    return (
        room.bookings.filter(status=OrBookingStatus.BOOKED, starts_at__lt=ends_at, ends_at__gt=starts_at)
        .order_by("starts_at")
        .first()
    )


def _overlap_error(room: OperatingRoom, clash: OrBooking) -> dict:
    start, end = timezone.localtime(clash.starts_at), timezone.localtime(clash.ends_at)
    return {"startsAt": [f"{room.name} is already booked from {start:%H:%M} to {end:%H:%M}."]}


@transaction.atomic
def book_operating_room(data: dict, *, actor) -> OrBooking:
    """Book a slot in the room `data["roomId"]`. The room row is locked, so bookings for one room queue up on
    every database. The DB exclusion constraint is the backstop: it catches a clash the check missed."""
    room = get_object_or_404(OperatingRoom.objects.select_for_update(), pk=data["roomId"])
    if not may_change(actor, room):
        raise Http404
    if room.status == OrStatus.OUT_OF_SERVICE:
        raise ValidationError({"roomId": [f"{room.name} is out of service."]})
    starts_at, ends_at = data["startsAt"], data["endsAt"]
    if clash := _clash(room, starts_at, ends_at):
        raise ValidationError(_overlap_error(room, clash))
    try:
        with transaction.atomic():
            booking = OrBooking.objects.create(
                room=room,
                booked_by=actor,
                starts_at=starts_at,
                ends_at=ends_at,
                procedure=data["procedure"],
                surgeon=data["surgeon"],
                patient_initials=data["patientInitials"],
            )
    except IntegrityError:
        clash = _clash(room, starts_at, ends_at)
        if clash is None:  # not an overlap after all
            raise
        raise ValidationError(_overlap_error(room, clash)) from None
    record(
        actor,
        "orbooking.created",
        booking,
        after={
            "room": room.name,
            "startsAt": starts_at.isoformat(),
            "endsAt": ends_at.isoformat(),
            "procedure": booking.procedure,
        },
    )
    return booking


def may_cancel(user, booking: OrBooking) -> bool:
    """Admins and nurses coordinate the theatres, so they can cancel any booking they can see. Anyone else who
    books (surgeons) can cancel only their own. The own-hospital rule is checked separately."""
    return user.effective_role in (Role.ADMIN, Role.NURSE) or booking.booked_by_id == user.id


@transaction.atomic
def cancel_operating_booking(booking_id: int, *, actor) -> OrBooking:
    """Cancel a booked slot. The row is kept (status cancelled), so the room's history stays readable, and the
    slot can be booked again. Another hospital's booking is a 404."""
    booking = get_object_or_404(
        OrBooking.objects.select_for_update(of=("self",)).select_related("room"), pk=booking_id
    )
    if not may_change(actor, booking.room):
        raise Http404
    if not may_cancel(actor, booking):
        raise PermissionDenied("You can only cancel bookings you made.")
    if booking.status != OrBookingStatus.BOOKED:
        raise TransitionNotAllowed("This booking is already cancelled.")
    booking.status = OrBookingStatus.CANCELLED
    booking.save(update_fields=["status"])
    record(
        actor,
        "orbooking.cancelled",
        booking,
        before={"status": OrBookingStatus.BOOKED},
        after={"status": OrBookingStatus.CANCELLED},
    )
    return booking


def day_schedule(user, day: date) -> dict:
    """Every room in the user's hospital (every room for users without one) with its booked slots that overlap
    the local calendar day `day`, in time order. A booking that runs past midnight shows on both days."""
    start = timezone.make_aware(datetime.combine(day, time.min))
    end = start + timedelta(days=1)
    rooms = OperatingRoom.objects.all()
    if user.hospital_id:
        rooms = rooms.filter(hospital_id=user.hospital_id)
    rooms = list(rooms.order_by("name"))
    bookings = (
        OrBooking.objects.filter(
            room__in=rooms, status=OrBookingStatus.BOOKED, starts_at__lt=end, ends_at__gt=start
        )
        .select_related("booked_by")
        .order_by("starts_at")
    )
    by_room = defaultdict(list)
    for booking in bookings:
        by_room[booking.room_id].append(OrBookingSerializer(booking, context={"user": user}).data)
    return {
        "date": day.isoformat(),
        "rooms": [
            {
                "id": room.id,
                "name": room.name,
                "status": room.status,
                "capabilities": room.capabilities,
                "bookings": by_room[room.id],
            }
            for room in rooms
        ],
    }
