"""What the simulation tells people (B21): its own event list for the CityCare admin, and the few alerts staff
must act on, rate-limited so they never flood."""

from datetime import datetime, timedelta

from django.utils import timezone

from apps.notifications.models import Severity
from apps.notifications.services import notify

from .models import SimEvent

ALERT_GAP_CITY = timedelta(minutes=30)  # at most one alert of a kind per hospital per 30 minutes of city time
ALERT_GAP_REAL = timedelta(minutes=2)  # ...and per 2 real minutes, so a fast clock doesn't flood either


def log(at: datetime, kind: str, message: str, hospital=None) -> SimEvent:
    return SimEvent.objects.create(at=at, hospital=hospital, kind=kind, message=message[:300])


def alert(state, *, at: datetime, kind: str, hospital, module: str, message: str, link: str, actor) -> bool:
    """Notify `hospital`'s staff who can act in `module`, unless the same kind of alert went there recently.
    Returns whether it went. `state.alerts_sent` is saved by the caller with the tick."""
    key = f"{hospital.pk}:{kind}"
    last = state.alerts_sent.get(key)
    real = timezone.now()
    if last:
        city_last, real_last = (datetime.fromisoformat(v) for v in last)
        if at - city_last < ALERT_GAP_CITY or real - real_last < ALERT_GAP_REAL:
            return False
    notify(
        f"simulation.{kind}",
        hospital=hospital,
        module=module,
        message=message,
        link=link,
        severity=Severity.CRITICAL,
        actor=actor,
    )
    state.alerts_sent[key] = [at.isoformat(), real.isoformat()]
    return True
