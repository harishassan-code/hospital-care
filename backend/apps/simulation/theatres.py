"""Operating theatres, five minutes at a time (B21): each room's list for the next day is booked overnight and
a share of it cancelled; a booked case starts when its room is free, runs to about its planned end, and the
room is cleaned (20-40 minutes) before it is available again. Now and then an emergency case takes a free
room."""

from datetime import datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.seed.resources import LETTERS, PROCEDURES, poisson
from apps.operating_rooms.models import OperatingRoom, OrBooking, OrBookingStatus, OrStatus
from apps.operating_rooms.services import book_operating_room, cancel_operating_booking
from apps.resources.services import change_status
from apps.specialists.models import Specialist
from apps.staffing.models import StaffMember, StaffRole

from . import events
from .world import Site, stable

LIST_START, LIST_END = time(8), time(17)
CLEANING = (20, 40)
OVERRUN = (-10, 40)
EMERGENCY_CASE = (60, 180)
LATE_START = timedelta(hours=2)  # a case whose room is still busy two hours after its start is dropped


def _room(pk):
    return OperatingRoom.objects.select_for_update().get(pk=pk)


def _running_booking(room: OperatingRoom):
    return (
        OrBooking.objects.filter(
            room=room,
            status=OrBookingStatus.BOOKED,
            starts_at__lte=room.status_since + timedelta(minutes=5),
            ends_at__gt=room.status_since - LATE_START,
        )
        .order_by("-starts_at")
        .first()
    )


def case_ends_at(room: OperatingRoom):
    booking = _running_booking(room)
    if booking is not None:
        late = max(timedelta(0), room.status_since - booking.starts_at)
        return booking.ends_at + late + timedelta(minutes=stable("overrun", booking.pk).uniform(*OVERRUN))
    return room.status_since + timedelta(
        minutes=stable("case", room.pk, room.status_since.isoformat()).uniform(*EMERGENCY_CASE)
    )


def _move(room: OperatingRoom, action: str, tick, reason: str) -> bool:
    with transaction.atomic():
        locked = _room(room.pk)
        if locked.status != room.status:
            return False
        change_status(locked, action, actor=tick.actor, reason=reason)
    return True


def step(site: Site, tick, start, end, held: set[int]) -> None:
    if not site.rooms:
        return
    rand = tick.rand
    minutes = (end - start).total_seconds() / 60
    rooms = list(OperatingRoom.objects.filter(hospital=site.hospital).exclude(pk__in=held))
    for room in rooms:
        if room.status == OrStatus.IN_USE and case_ends_at(room) <= end:
            _move(room, "finishCase", tick, "Case finished")
        elif room.status == OrStatus.CLEANING:
            done = room.status_since + timedelta(
                minutes=stable("or-clean", room.pk, room.status_since.isoformat()).uniform(*CLEANING)
            )
            if done <= end:
                _move(room, "finishCleaning", tick, "Cleaned and set up")
    for room in OperatingRoom.objects.filter(hospital=site.hospital, status=OrStatus.AVAILABLE).exclude(
        pk__in=held
    ):
        booking = (
            OrBooking.objects.filter(
                room=room, status=OrBookingStatus.BOOKED, starts_at__lte=end, starts_at__gt=end - LATE_START
            )
            .order_by("starts_at")
            .first()
        )
        if booking is not None and booking.ends_at > end:
            _move(room, "startCase", tick, f"Started: {booking.procedure}")
    # An emergency case takes a free room now and then (more during a mass-casualty event).
    rate = (
        site.rooms * tick.emergency_theatre / 1440 * minutes
        + tick.theatre_surge.get(site.hospital.pk, 0) * minutes / 60
    )
    for _ in range(poisson(rand, rate)):
        free = [
            r
            for r in OperatingRoom.objects.filter(hospital=site.hospital, status=OrStatus.AVAILABLE).exclude(
                pk__in=held
            )
            if not OrBooking.objects.filter(
                room=r, status=OrBookingStatus.BOOKED, starts_at__lt=end + timedelta(hours=2), ends_at__gt=end
            ).exists()
        ]
        if not free:
            break
        room = rand.choice(free)
        if _move(room, "startCase", tick, "Emergency case"):
            events.log(
                end, "or.emergency", f"{site.hospital.name}: emergency case in {room.name}.", site.hospital
            )


def _surgeons(hospital) -> list[str]:
    names = list(
        StaffMember.objects.filter(
            hospital=hospital, role=StaffRole.DOCTOR, department__icontains="surg"
        ).values_list("name", flat=True)[:12]
    )
    return names or list(Specialist.objects.filter(hospital=hospital).values_list("name", flat=True)[:8])


def book_lists(site: Site, tick, day) -> int:
    """Book each room's elective list for `day` (08:00 to about 17:00, cases of one to three hours with half
    an hour between), unless the room already has bookings that day, then cancel the scenario's share of them.
    Through the booking service, so every booking is checked and audit-logged."""
    if not site.rooms:
        return 0
    rand = stable("lists", site.hospital.pk, day.isoformat(), tick.state.seed)
    surgeons = _surgeons(site.hospital)
    made = 0
    for room in OperatingRoom.objects.filter(hospital=site.hospital).exclude(
        status__in=(OrStatus.MAINTENANCE, OrStatus.OUT_OF_SERVICE)
    ):
        start_of_day = timezone.make_aware(datetime.combine(day, time(0)))
        if OrBooking.objects.filter(
            room=room, starts_at__gte=start_of_day, starts_at__lt=start_of_day + timedelta(days=1)
        ).exists():
            continue
        procedures = [p for cap in room.capabilities for p in PROCEDURES.get(cap, [])] or PROCEDURES[
            "general"
        ]
        weekend = day.weekday() == 6
        at = timezone.make_aware(datetime.combine(day, LIST_START))
        end_of_list = timezone.make_aware(datetime.combine(day, LIST_END))
        booked = []
        while at < end_of_list and not weekend:
            length = timedelta(minutes=rand.choice([60, 90, 120, 150, 180]))
            if at + length > end_of_list + timedelta(minutes=30):
                break
            if rand.random() < tick.list_fill:
                booked.append(
                    book_operating_room(
                        {
                            "roomId": room.pk,
                            "startsAt": at,
                            "endsAt": at + length,
                            "procedure": rand.choice(procedures),
                            "surgeon": rand.choice(surgeons) if surgeons else "",
                            "patientInitials": f"{rand.choice(LETTERS)}.{rand.choice(LETTERS)}.",
                        },
                        actor=tick.actor,
                    )
                )
            at += length + timedelta(minutes=30)
        made += len(booked)
        for booking in booked:
            if rand.random() < tick.cancel:
                cancel_operating_booking(booking.pk, actor=tick.actor)
    return made
