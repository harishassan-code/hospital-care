from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("Audit entries can't be changed.")

    def delete(self):
        raise PermissionError("Audit entries can't be deleted.")


class AuditLog(models.Model):
    """
    One critical action: who did what to which object, when, why, and the values before and after.
    Append-only: the model refuses updates and deletes, and no API endpoint writes it.
    Written through apps.audit.services.record.
    """

    at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Kept even if the account is deleted later: the email is copied into actor_email.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    actor_email = models.CharField(max_length=254, blank=True)
    action = models.CharField(max_length=60, help_text='"<object>.<verb>", e.g. "hospital.updated".')
    target_type = models.CharField(max_length=100, help_text='"<app>.<model>", e.g. "hospitals.hospital".')
    target_id = models.CharField(max_length=64)
    target_repr = models.CharField(max_length=200)
    before = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    after = models.JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    reason = models.CharField(max_length=300, blank=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-at", "-id"]
        indexes = [models.Index(fields=["target_type", "target_id"])]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.actor_email or 'system'} {self.action} {self.target_repr}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Audit entries can't be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit entries can't be deleted.")
