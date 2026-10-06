from django.db import models


class ErStatus(models.TextChoices):
    ACCEPTING = "accepting", "Accepting patients"
    BUSY = "busy", "Very busy"
    DIVERTING = "diverting", "Not accepting ambulances"


class EmergencyStatus(models.Model):
    """The emergency department's current public status. A single row (pk=1), edited by staff."""

    status = models.CharField(max_length=20, choices=ErStatus.choices, default=ErStatus.ACCEPTING)
    wait_minutes = models.PositiveIntegerField(default=0)
    waiting_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "emergency status"

    def __str__(self):
        return self.get_status_display()

    @classmethod
    def current(cls) -> "EmergencyStatus":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
