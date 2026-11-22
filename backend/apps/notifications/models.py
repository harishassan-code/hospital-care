"""In-app notifications (story #52; bolt B06). One row per recipient, written by `notify` when a domain event
happens. Read state belongs to that one person, so the row is theirs alone. The rules are in services.py."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Severity(models.TextChoices):
    """`critical` needs an answer soon (the banner in B07). Everything else is `info`."""

    CRITICAL = "critical", "Critical"
    INFO = "info", "Info"


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=40, help_text='The event, e.g. "transfer.requested".')
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.INFO)
    message = models.CharField(max_length=300)
    link = models.CharField(
        max_length=200, blank=True, help_text='A staff page path, e.g. "/staff/transfers".'
    )
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(null=True, blank=True, help_text="Empty until the person marks it read.")

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["user", "read_at"], name="notifications_user_read")]

    def __str__(self):
        return f"{self.kind} for {self.user_id}"
