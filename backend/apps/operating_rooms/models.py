from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from apps.resources.models import Resource
from apps.resources.state_machine import StateMachine


class OrCapability(models.TextChoices):
    """What a room is equipped for, so a suitable room can be found (story #28)."""

    GENERAL = "general", "General"
    CARDIAC = "cardiac", "Cardiac"
    TRAUMA = "trauma", "Trauma"
    NEURO = "neuro", "Neuro"
    ORTHOPEDIC = "orthopedic", "Orthopedic"
    OBSTETRIC = "obstetric", "Obstetric"
    PEDIATRIC = "pediatric", "Pediatric"


class OrStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    IN_USE = "inUse", "In use"
    CLEANING = "cleaning", "Cleaning"
    RESERVED = "reserved", "Reserved"
    MAINTENANCE = "maintenance", "Maintenance"
    OUT_OF_SERVICE = "outOfService", "Out of service"


S = OrStatus

# Status changes go through POST /api/operating-rooms/<id>/actions/ (story #28). "reserve" and
# "cancelReservation" are also what a hold made by the reservation service does (story #43).
OR_LIFECYCLE = StateMachine(
    "room",  # for the 409 message: "Can't startCase a room that is in use."
    OrStatus,
    {
        (S.AVAILABLE, "startCase"): S.IN_USE,
        (S.AVAILABLE, "reserve"): S.RESERVED,
        (S.RESERVED, "cancelReservation"): S.AVAILABLE,
        (S.RESERVED, "startCase"): S.IN_USE,
        (S.IN_USE, "finishCase"): S.CLEANING,
        (S.CLEANING, "finishCleaning"): S.AVAILABLE,
        (S.AVAILABLE, "startMaintenance"): S.MAINTENANCE,
        (S.CLEANING, "startMaintenance"): S.MAINTENANCE,
        (S.MAINTENANCE, "finishMaintenance"): S.AVAILABLE,
        (S.AVAILABLE, "outOfService"): S.OUT_OF_SERVICE,
        (S.MAINTENANCE, "outOfService"): S.OUT_OF_SERVICE,
        (S.OUT_OF_SERVICE, "returnToService"): S.MAINTENANCE,
    },
)


class OperatingRoomQuerySet(models.QuerySet):
    def matchable(self):
        """Only rooms free right now. The matching engine calls this, so rooms in use, being cleaned, in
        maintenance or out of service are never matched."""
        return self.filter(status=OrStatus.AVAILABLE)

    def with_capability(self, code: str):
        """Rooms equipped for `code`. `capabilities` is a JSON list and SQLite has no JSON "contains", so this
        matches the quoted code inside the stored JSON text. Quotes stop "cardiac" matching a longer code.
        ponytail: a text match, not a JSON query. Fine at per-hospital room counts; switch to a join table
        if rooms ever need to be searched across the whole network."""
        return self.filter(capabilities__icontains=f'"{code}"')


class OperatingRoom(Resource):
    """One operating theatre, e.g. "Cardiac theatre" in Block B, floor 2 (story #28)."""

    machine = OR_LIFECYCLE
    objects = OperatingRoomQuerySet.as_manager()

    name = models.CharField(
        max_length=60, help_text='e.g. "OR 1" or "Cardiac theatre". Unique within a hospital.'
    )
    capabilities = models.JSONField(default=list, help_text="Codes from OrCapability, e.g. cardiac, trauma.")
    location = models.CharField(
        max_length=120, blank=True, help_text='Where to find it, e.g. "Block B, floor 2".'
    )
    status = models.CharField(max_length=20, choices=OrStatus.choices, default=OrStatus.AVAILABLE)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "operating rooms"
        constraints = [
            models.UniqueConstraint(
                "hospital",
                Lower("name"),
                nulls_distinct=False,  # unique for network-level (no hospital) rows too
                name="operating_room_name_unique_per_hospital",
            )
        ]

    def __str__(self):
        return self.name


class OrBookingStatus(models.TextChoices):
    BOOKED = "booked", "Booked"
    CANCELLED = "cancelled", "Cancelled"


class OrBooking(models.Model):
    """A booked time slot in one operating room (story #29). Times are half-open: [starts_at, ends_at)."""

    room = models.ForeignKey(OperatingRoom, on_delete=models.PROTECT, related_name="bookings")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    procedure = models.CharField(max_length=120)
    surgeon = models.CharField(max_length=120, blank=True)
    patient_initials = models.CharField(max_length=10, blank=True)  # minimal patient data, as for Bed
    status = models.CharField(max_length=10, choices=OrBookingStatus.choices, default=OrBookingStatus.BOOKED)
    booked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=F("starts_at")), name="or_booking_ends_after_start"
            ),
            # No-overlap is a Postgres EXCLUDE constraint, or_booking_no_overlap_per_room, added in migration
            # 0002 and kept out of Meta so SQLite, which can't run it, never rebuilds the table with it.
        ]

    def __str__(self):
        return self.procedure
