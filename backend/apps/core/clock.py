"""The city clock (B21). Everything the app records and shows asks this module for the time, not Django:
with the simulation off it is exactly `timezone.now()`; with it on, the CityCare admin can pause it, run it
faster or slower, or fast-forward it (apps/simulation). Sign-in sessions, sign-in limits and the cache keep
the real clock, because they use Django's own `timezone.now()`.

The state is read from the database at most once a second per process, so every copy of the app on Vercel
agrees within a second, and a busy request doesn't query it more than once.
"""

import threading
import time as _time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

REFRESH_SECONDS = 1.0


@dataclass(frozen=True)
class Reading:
    """The clock's settings at one moment."""

    enabled: bool = False
    paused: bool = False
    speed: float = 1.0
    anchor_real: datetime | None = None
    anchor_city: datetime | None = None
    progress: datetime | None = None
    fast_forward_to: datetime | None = None

    @property
    def mode(self) -> str:
        if not self.enabled:
            return "real"
        if self.fast_forward_to is not None:
            return "fastForward"
        if self.paused:
            return "paused"
        return "live"

    def city(self, real: datetime) -> datetime:
        if not self.enabled or self.anchor_real is None or self.anchor_city is None:
            return real
        if self.fast_forward_to is not None and self.progress is not None:
            return self.progress
        if self.paused:
            return self.anchor_city
        return self.anchor_city + (real - self.anchor_real) * self.speed


_cache: dict = {"at": 0.0, "reading": Reading()}
_lock = threading.Lock()


def reading(*, fresh: bool = False) -> Reading:
    """The clock's settings, at most a second old (or read now with `fresh`)."""
    if not getattr(settings, "SIMULATION_ENABLED", False):
        return Reading()
    with _lock:
        if not fresh and _time.monotonic() - _cache["at"] < REFRESH_SECONDS:
            return _cache["reading"]
    from apps.simulation.models import SimulationState  # the clock is used everywhere; import late

    try:
        state = SimulationState.objects.filter(pk=1).first()
    except DatabaseError:  # before migrate, or the table is gone: real time
        state = None
    value = (
        Reading()
        if state is None or not state.enabled
        else Reading(
            enabled=True,
            paused=state.paused,
            speed=state.speed,
            anchor_real=state.anchor_real,
            anchor_city=state.anchor_city,
            progress=state.progress,
            fast_forward_to=state.fast_forward_to,
        )
    )
    with _lock:
        _cache.update(at=_time.monotonic(), reading=value)
    return value


def forget():
    """Read the state again next time (after the admin changes it, and in tests)."""
    with _lock:
        _cache["at"] = 0.0


def real_now() -> datetime:
    return timezone.now()


_override = threading.local()


@contextmanager
def at(moment: datetime):
    """Inside this block, `now()` is `moment`: the simulation stamps what happens in a step with the step's
    time, not the time the engine happened to run it."""
    previous = getattr(_override, "moment", None)
    _override.moment = moment
    try:
        yield moment
    finally:
        _override.moment = previous


def now() -> datetime:
    """The city's time: the real time unless the simulation runs its own clock."""
    moment = getattr(_override, "moment", None)
    if moment is not None:
        return moment
    real = timezone.now()
    if not getattr(settings, "SIMULATION_ENABLED", False):
        return real
    return reading().city(real)


def localdate() -> date:
    """Today, on the city clock, in the city's time zone (Karachi)."""
    return timezone.localdate(now())


def localtime() -> datetime:
    return timezone.localtime(now())
