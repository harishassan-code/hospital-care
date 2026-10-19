from django.db import models
from django.utils import timezone

from .state_machine import StateMachine


class Resource(models.Model):
    """
    What every shared resource has: the hospital that owns it, where it's stored, and when its status last
    changed. Subclasses add their own `status` field (with their choices) and a `machine` (StateMachine).
    Status changes go through apps.resources.services.change_status, never by setting `status` directly.
    """

    machine: StateMachine

    # Nullable only for rows from before Sprint 2; seed_demo backfills them. New rows always get one.
    hospital = models.ForeignKey(
        "hospitals.Hospital", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    storage_location = models.ForeignKey(
        "hospitals.StorageLocation", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    status_since = models.DateTimeField(default=timezone.now)

    class Meta:
        abstract = True
