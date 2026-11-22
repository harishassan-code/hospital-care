from django.conf import settings
from django.db import models
from django.utils import timezone


class Severity(models.TextChoices):
    INFO = "info", "Info"
    WARNING = "warning", "Warning"
    CRITICAL = "critical", "Critical"


class Notification(models.Model):
    """
    One event for the staff of one hospital (story #52). Addressed to a hospital and a set of roles, not to
    users: who reads it is decided when they ask (fan-out on read), so staff changes need no backfill.
    `hospital` None means the whole network (admins only). Written through apps.notifications.services.notify.
    """

    hospital = models.ForeignKey(
        "hospitals.Hospital", on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    roles = models.CharField(
        max_length=120, blank=True, help_text='Role ids as ",doctor,nurse,"; empty means every staff role.'
    )
    kind = models.CharField(max_length=40, help_text='"<object>.<event>", e.g. "transfer.requested".')
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=300, blank=True)
    link = models.CharField(max_length=200, blank=True, help_text="Frontend path, e.g. /staff/transfers.")
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["hospital", "created_at"])]

    def __str__(self):
        return self.title


class NotificationReceipt(models.Model):
    """What one user did with one notification: read it, and (critical ones) acknowledged it."""

    notification = models.ForeignKey(Notification, on_delete=models.CASCADE, related_name="receipts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    read_at = models.DateTimeField(null=True, blank=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["notification", "user"], name="notification_receipt_unique")
        ]

    def __str__(self):
        return f"{self.user_id} · {self.notification_id}"
