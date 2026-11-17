"""Reservations (stories #43, #44) and allocations (#45): one resource held for one need of one emergency
case, and the record of handing it over. The ERD's Reservation and Allocation.

The resource is any Resource subclass (a blood unit, a bed, a piece of equipment, an operating room), found
through a content type and an id. The partial unique constraint is the database's guarantee that a resource
has at most one active hold. The rules for making and ending holds are in reservations.py."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ReservationStatus(models.TextChoices):
    HELD = "held", "Held"
    ALLOCATED = "allocated", "Allocated"  # set by allocation (#45); the hold became an Allocation
    RELEASED = "released", "Released"
    EXPIRED = "expired", "Expired"


ACTIVE = (ReservationStatus.HELD, ReservationStatus.ALLOCATED)


class Reservation(models.Model):
    request_item = models.ForeignKey(
        "emergencies.RequestItem", on_delete=models.PROTECT, related_name="reservations"
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.PositiveBigIntegerField()
    resource = GenericForeignKey("content_type", "object_id")
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="+")
    status = models.CharField(
        max_length=10, choices=ReservationStatus.choices, default=ReservationStatus.HELD
    )
    reserved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(
        help_text="When an unused hold is released. Set from RESERVATION_HOLD_MINUTES."
    )
    ended_at = models.DateTimeField(null=True, blank=True)
    end_reason = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["status", "expires_at"], name="matching_reservation_expiry")]
        constraints = [
            # One active hold per resource. A released or expired hold doesn't count, so the resource can be
            # held again.
            models.UniqueConstraint(
                fields=["content_type", "object_id"],
                condition=Q(status__in=ACTIVE),
                name="matching_one_active_reservation_per_resource",
            )
        ]

    def __str__(self):
        return f"{self.content_type.model} {self.object_id}: {self.status}"


class Allocation(models.Model):
    """The permanent record that a held resource was handed over (story #45). One per reservation.

    It copies the resource's content type and id, the need, the case and the supplying hospital, so it stands
    alone. There is no endpoint to change or delete one, and the admin is read-only. Every foreign key is
    PROTECT, so nothing it names can be deleted under it."""

    reservation = models.OneToOneField(Reservation, on_delete=models.PROTECT, related_name="allocation")
    request = models.ForeignKey(
        "emergencies.EmergencyRequest", on_delete=models.PROTECT, related_name="allocations"
    )
    request_item = models.ForeignKey(
        "emergencies.RequestItem", on_delete=models.PROTECT, related_name="allocations"
    )
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="+")
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.PositiveBigIntegerField()
    resource = GenericForeignKey("content_type", "object_id")
    allocated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    at = models.DateTimeField(default=timezone.now)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["at", "id"]

    def __str__(self):
        return f"{self.request_id}: {self.content_type.model} {self.object_id} allocated"
