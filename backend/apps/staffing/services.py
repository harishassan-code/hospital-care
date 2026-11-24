"""Clocking in and out, who is on duty, and keeping the rota a week ahead (B21). The simulation clocks staff
in and out on staging; a hospital's own time clock would call the same functions."""

from collections import Counter
from datetime import timedelta

from django.db import transaction

from apps.audit.services import record
from apps.core import clock

from .models import Shift

AHEAD_DAYS = 7


@transaction.atomic
def clock_in(shift: Shift, *, at, actor) -> Shift:
    shift = Shift.objects.select_for_update().get(pk=shift.pk)
    if shift.clocked_in_at is None:
        shift.clocked_in_at = at
        shift.save(update_fields=["clocked_in_at"])
        record(actor, "shift.clocked_in", shift, after={"at": at.isoformat()})
    return shift


@transaction.atomic
def clock_out(shift: Shift, *, at, actor) -> Shift:
    shift = Shift.objects.select_for_update().get(pk=shift.pk)
    if shift.clocked_in_at is not None and shift.clocked_out_at is None:
        shift.clocked_out_at = max(at, shift.clocked_in_at)
        shift.save(update_fields=["clocked_out_at"])
        record(actor, "shift.clocked_out", shift, after={"at": shift.clocked_out_at.isoformat()})
    return shift


def on_duty(hospital, at=None, *, department: str | None = None) -> Counter:
    """How many doctors and nurses are clocked in at `hospital` now: {"doctor": n, "nurse": n}."""
    at = at or clock.now()
    shifts = Shift.objects.filter(hospital=hospital).on_duty_at(at)
    if department:
        shifts = shifts.filter(staff__department=department)
    return Counter(shifts.values_list("staff__role", flat=True))


def rostered(hospital, at=None, *, department: str | None = None) -> Counter:
    """How many doctors and nurses the rota plans for `hospital` now, whether or not they came."""
    at = at or clock.now()
    shifts = Shift.objects.filter(hospital=hospital).covering(at)
    if department:
        shifts = shifts.filter(staff__department=department)
    return Counter(shifts.values_list("staff__role", flat=True))


def extend_rota(today, *, days: int = AHEAD_DAYS) -> int:
    """Keep every rota `days` ahead: a day with no shifts yet repeats the same weekday a week earlier (the
    rota is weekly). Returns how many shifts were added."""
    added = []
    for offset in range(1, days + 1):
        day = today + timedelta(days=offset)
        have = set(Shift.objects.filter(starts_at__date=day).values_list("staff_id", flat=True).distinct())
        week_before = Shift.objects.filter(
            starts_at__date=day - timedelta(days=7), staff__is_active=True
        ).exclude(staff_id__in=have)
        added += [
            Shift(
                staff_id=s.staff_id,
                hospital_id=s.hospital_id,
                starts_at=s.starts_at + timedelta(days=7),
                ends_at=s.ends_at + timedelta(days=7),
            )
            for s in week_before
        ]
    Shift.objects.bulk_create(added, batch_size=2000)
    return len(added)
