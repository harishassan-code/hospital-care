"""A hospital's emergency department status (B19): what the public sees for that hospital, changed only by
that hospital's staff (and, on staging, by the simulation in B21). Every change is audit-logged."""

from django.db import transaction

from apps.audit.services import record
from apps.core import clock

from .models import EmergencyStatus

# Upper bounds a person can enter; anything above is a typo, not a waiting room.
MAX_WAIT_MINUTES = 24 * 60
MAX_WAITING = 999


def _fields(status: EmergencyStatus) -> dict:
    return {"status": status.status, "waitMinutes": status.wait_minutes, "waitingCount": status.waiting_count}


def department_status(hospital) -> EmergencyStatus | None:
    """The hospital's status, or None if it has never reported one."""
    return EmergencyStatus.objects.filter(hospital=hospital).first()


@transaction.atomic
def update_department_status(
    *,
    hospital,
    status: str,
    wait_minutes: int,
    waiting_count: int,
    actor,
    log_minor: bool = True,
    factors=None,
):
    """Set the hospital's status, wait and number waiting. Logged as `er_status.updated` when anything
    changed; with `log_minor` off (the simulation, every five minutes), only when the status itself changed,
    so the trail isn't one entry per minute of wait."""
    current = EmergencyStatus.objects.select_for_update().filter(hospital=hospital).first()
    before = None if current is None else _fields(current)
    if current is None:
        current = EmergencyStatus(hospital=hospital)
    current.status, current.wait_minutes, current.waiting_count = status, wait_minutes, waiting_count
    current.updated_at, current.set_by, current.factors = clock.now(), actor, factors or []
    current.save()
    after = _fields(current)
    changed = after != before if log_minor else (before or {}).get("status") != after["status"]
    if changed:
        record(actor, "er_status.updated", hospital, before=before, after=after)
    return current
