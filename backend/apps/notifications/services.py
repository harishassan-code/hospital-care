"""In-app notifications (story #52; bolt B06). Domain code calls `notify` next to its audit record and
names the hospital and the module. This module picks the people and the channels; the domain never does.
It imports nothing from the domain apps, so there are no import cycles."""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.permissions import can_edit
from apps.audit.services import record

from .channels import CHANNELS
from .models import Notification, Severity

# The most rows the list returns. The list is not paged in the MVP.
LIST_LIMIT = 50
MESSAGE_MAX = 300


def recipients(hospital, module: str):
    """Active users at `hospital` whose role can edit `module`. A superuser counts as an admin."""
    roles = [role for role in Role.values if can_edit(role, module)]
    who = Q(role__in=roles)
    if Role.ADMIN in roles:
        who |= Q(is_superuser=True)
    return get_user_model().objects.filter(who, is_active=True, hospital=hospital)


def notify(
    kind: str,
    *,
    hospital,
    module: str,
    message: str,
    link: str,
    severity: str = Severity.INFO,
    actor=None,
) -> list[Notification]:
    """Tell the staff at `hospital` who can edit `module` about one event: one row per recipient, handed to
    every channel. Nothing is created when `hospital` is None. The actor, who made the move, is left out.
    Call it inside the move's transaction, so a rolled-back move sends nothing."""
    if hospital is None:
        return []
    people = recipients(hospital, module)
    if actor is not None and actor.pk is not None:
        people = people.exclude(pk=actor.pk)
    rows = Notification.objects.bulk_create(
        Notification(
            user=person,
            kind=kind,
            severity=severity,
            message=message[:MESSAGE_MAX],
            link=link,
        )
        for person in people
    )
    for row in rows:
        for channel in CHANNELS:
            channel.send(row)
    return rows


def inbox(user, *, unread_only: bool = False):
    """The user's own notifications, newest first, at most LIST_LIMIT. Never another user's rows."""
    rows = Notification.objects.filter(user=user)
    if unread_only:
        rows = rows.filter(read_at__isnull=True)
    return rows.order_by("-created_at", "-id")[:LIST_LIMIT]


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


@transaction.atomic
def mark_read(pk: int, *, user) -> Notification:
    """Mark one of the user's notifications read. `read_at` is set once: a second call returns the row as it
    is, with the first time, and writes no audit record (nothing changed). The first call writes
    `notification.read`. Another user's row is a 404, as if it didn't exist."""
    row = Notification.objects.select_for_update().filter(pk=pk, user=user).first()
    if row is None:
        raise Http404("No notification with that id.")
    if row.read_at is None:
        row.read_at = timezone.now()
        row.save(update_fields=["read_at"])
        record(user, "notification.read", row, before={"read": False}, after={"read": True})
    return row
