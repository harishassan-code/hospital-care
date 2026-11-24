"""Doctors and nurses clocking in and out (B21). Each shift's fate is decided once, from its own random
stream: most start within ten minutes of time, some 15-45 minutes late, a few not at all (absent); everyone
clocks out within about 20 minutes of the end."""

from datetime import timedelta

from apps.staffing.models import Shift
from apps.staffing.services import clock_in, clock_out

from .world import stable

LOOK_BACK = timedelta(hours=2)  # a shift more than two hours past its start with no clock-in was missed


def clock_in_time(shift: Shift, tick):
    """When this shift's person clocks in, or None if they don't come."""
    rand = stable("shift", shift.pk, tick.state.seed)
    roll = rand.random()
    if roll < tick.absent:
        return None
    if roll < tick.absent + tick.late:
        return shift.starts_at + timedelta(minutes=rand.uniform(15, 45))
    return shift.starts_at + timedelta(minutes=rand.uniform(-12, 8))


def clock_out_time(shift: Shift):
    return shift.ends_at + timedelta(minutes=stable("out", shift.pk).uniform(0, 25))


def step(tick, start, end, hospitals, *, audit: bool = True) -> int:
    """Clock people in and out up to `end`. With `audit` off (a fast-forward hour), the times are written in
    bulk without an audit entry each. Returns how many shifts changed."""
    changed = []
    starting = Shift.objects.filter(
        hospital__in=hospitals,
        clocked_in_at__isnull=True,
        starts_at__gt=end - LOOK_BACK,
        starts_at__lte=end + timedelta(minutes=15),
    )
    for shift in starting:
        at = clock_in_time(shift, tick)
        if at is None:
            if (
                shift.starts_at + timedelta(minutes=45) <= end
                and shift.starts_at + timedelta(minutes=45) > start
            ):
                tick.count_absent(shift.hospital_id)
            continue
        if at <= end:
            at = min(at, end)
            if audit:
                clock_in(shift, at=at, actor=tick.actor)
            else:
                shift.clocked_in_at = at
                changed.append(shift)
    ending = Shift.objects.filter(
        hospital__in=hospitals,
        clocked_in_at__isnull=False,
        clocked_out_at__isnull=True,
        ends_at__lte=end,
    )
    for shift in ending:
        at = clock_out_time(shift)
        if at <= end or shift.ends_at + timedelta(hours=4) <= end:
            at = min(at, end)
            if audit:
                clock_out(shift, at=at, actor=tick.actor)
            else:
                shift.clocked_out_at = max(at, shift.clocked_in_at)
                changed.append(shift)
    if changed:
        Shift.objects.bulk_update(changed, ["clocked_in_at", "clocked_out_at"], batch_size=1000)
    return len(changed)
