"""In-app notifications from domain events (story #52). Other modules call `notify` next to their audit
record. Channels are the extension point: email or SMS is one more `Channel` subclass in CHANNELS."""

import logging

from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from apps.accounts.models import Role

from .models import Notification, NotificationReceipt, Severity

log = logging.getLogger(__name__)


class Channel:
    """Delivers a saved notification somewhere. Must not raise for a delivery problem it can retry."""

    def send(self, notification: Notification) -> None:
        raise NotImplementedError


class InAppChannel(Channel):
    """In-app delivery is the saved row itself: the bell reads it. Nothing more to do."""

    def send(self, notification: Notification) -> None:
        pass


CHANNELS: list[Channel] = [InAppChannel()]


def notify(
    *,
    hospital_id,
    kind: str,
    title: str,
    body: str = "",
    link: str = "",
    severity: str = Severity.INFO,
    roles: tuple[str, ...] = (),
) -> Notification | None:
    """Save a notification for `roles` at `hospital_id` (empty roles: all staff) and send it on every channel.
    Never breaks the action that caused it: a failure is logged and rolled back to a savepoint."""
    if roles and Role.ADMIN not in roles:
        roles = (*roles, Role.ADMIN)  # admins act for any hospital, so they hear about everything
    try:
        with transaction.atomic():
            notification = Notification.objects.create(
                hospital_id=hospital_id,
                roles=f",{','.join(roles)}," if roles else "",
                kind=kind,
                severity=severity,
                title=title[:160],
                body=body[:300],
                link=link,
            )
            for channel in CHANNELS:
                channel.send(notification)
            return notification
    except Exception:
        log.exception("Notification %s not sent", kind)
        return None


def for_user(user):
    """The notifications this user sees: their hospital's, for their role. Admins see what is addressed to
    admins (every event) at any hospital, plus network-wide ones. Annotated with read and acknowledged for
    this user."""
    role = user.effective_role
    if role == Role.PATIENT:
        return Notification.objects.none()
    role_match = Q(roles="") | Q(roles__contains=f",{role},")
    if role == Role.ADMIN:
        where = role_match
    elif user.hospital_id is None:
        return Notification.objects.none()
    else:
        where = role_match & Q(hospital_id=user.hospital_id)
    mine = NotificationReceipt.objects.filter(notification=OuterRef("pk"), user=user)
    return Notification.objects.filter(where).annotate(
        is_read=Exists(mine.filter(read_at__isnull=False)),
        is_acknowledged=Exists(mine.filter(acknowledged_at__isnull=False)),
    )


def _receipt(notification: Notification, user) -> NotificationReceipt:
    receipt, _ = NotificationReceipt.objects.get_or_create(notification=notification, user=user)
    return receipt


def mark_read(notification: Notification, user) -> None:
    receipt = _receipt(notification, user)
    if receipt.read_at is None:
        receipt.read_at = timezone.now()
        receipt.save(update_fields=["read_at"])


def mark_all_read(user) -> int:
    unread = list(for_user(user).filter(is_read=False))
    for notification in unread:
        mark_read(notification, user)
    return len(unread)


def acknowledge(notification: Notification, user) -> None:
    receipt = _receipt(notification, user)
    now = timezone.now()
    receipt.read_at = receipt.read_at or now
    receipt.acknowledged_at = receipt.acknowledged_at or now
    receipt.save(update_fields=["read_at", "acknowledged_at"])
