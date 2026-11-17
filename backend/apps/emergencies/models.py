from django.conf import settings
from django.db import models
from django.db.models import Case, Value, When
from django.utils import timezone

from apps.equipment.models import EquipmentType
from apps.operating_rooms.models import OrCapability
from apps.resources.state_machine import StateMachine


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


# ── Emergency cases (stories #30, #32) ────────────────────────────────────────────────────────────


class Severity(models.TextChoices):
    """Most severe first. The order here is the order lists sort by (see `by_priority`)."""

    CRITICAL = "critical", "Critical"
    HIGH = "high", "High"
    MODERATE = "moderate", "Moderate"
    LOW = "low", "Low"


class RequestStatus(models.TextChoices):
    """The lifecycle from the ERD. A new case is `open`; the moves are in REQUEST_LIFECYCLE."""

    OPEN = "open", "Open"
    MATCHING = "matching", "Matching"
    PARTIALLY_FULFILLED = "partiallyFulfilled", "Partially fulfilled"
    FULFILLED = "fulfilled", "Fulfilled"
    ESCALATED = "escalated", "Escalated"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Cancelled"


S = RequestStatus

# Story #34. Staff move cases by hand until allocation (#45) sets fulfilment. Closed and cancelled are final.
REQUEST_LIFECYCLE = StateMachine(
    "case",
    RequestStatus,
    {
        (S.OPEN, "startMatching"): S.MATCHING,
        (S.MATCHING, "partiallyFulfil"): S.PARTIALLY_FULFILLED,
        (S.MATCHING, "fulfil"): S.FULFILLED,
        (S.PARTIALLY_FULFILLED, "fulfil"): S.FULFILLED,
        (S.OPEN, "escalate"): S.ESCALATED,
        (S.MATCHING, "escalate"): S.ESCALATED,
        (S.PARTIALLY_FULFILLED, "escalate"): S.ESCALATED,
        (S.ESCALATED, "resumeMatching"): S.MATCHING,
        (S.FULFILLED, "close"): S.CLOSED,
        (S.PARTIALLY_FULFILLED, "close"): S.CLOSED,
        (S.ESCALATED, "close"): S.CLOSED,
        (S.OPEN, "cancel"): S.CANCELLED,
        (S.MATCHING, "cancel"): S.CANCELLED,
    },
)


def severity_rank(field: str = "severity"):
    """The position of a case's severity in `Severity`, 0 for the most severe.

    `field` is the path to the severity, so the rank can be read from a related case."""
    return Case(
        *[When(**{field: level}, then=Value(i)) for i, level in enumerate(Severity.values)],
        default=Value(len(Severity.values)),
        output_field=models.PositiveSmallIntegerField(),
    )


class EmergencyRequestQuerySet(models.QuerySet):
    def by_priority(self):
        """Most severe first, then the case waiting longest (oldest), then id so the order is stable."""
        return self.annotate(priority=severity_rank()).order_by("priority", "created_at", "id")


class EmergencyRequest(models.Model):
    """An emergency case and what it needs (story #30). Holds no patient-identifying data."""

    reference = models.CharField(max_length=16, unique=True, help_text='e.g. "EC-2026-0001". The API id.')
    hospital = models.ForeignKey(
        "hospitals.Hospital", on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    severity = models.CharField(max_length=10, choices=Severity.choices)
    status = models.CharField(max_length=20, choices=RequestStatus.choices, default=RequestStatus.OPEN)
    patient_ref = models.CharField(
        max_length=30, blank=True, help_text="Optional bed or triage tag. Never a name."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = EmergencyRequestQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.reference


class RequestStatusChange(models.Model):
    """One entry in a case's timeline (story #34). The first is the creation: "" to open, action "create"."""

    request = models.ForeignKey(EmergencyRequest, on_delete=models.CASCADE, related_name="history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, choices=RequestStatus.choices)
    action = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["at", "id"]
        verbose_name_plural = "request status changes"

    def __str__(self):
        return f"{self.request_id}: {self.from_status or '-'} → {self.to_status}"


class ResourceType(models.TextChoices):
    """What a case can ask for: blood, beds (#32), equipment (#26) and operating rooms (#28)."""

    BLOOD = "blood", "Blood"
    BED = "bed", "Bed"
    EQUIPMENT = "equipment", "Equipment"
    OPERATING_ROOM = "operatingRoom", "Operating room"


class RequestItem(models.Model):
    """One thing a case needs (story #32): blood, beds, equipment or operating rooms. Only the field of the
    item's own type is set; the others stay blank."""

    request = models.ForeignKey(EmergencyRequest, on_delete=models.CASCADE, related_name="items")
    resource_type = models.CharField(max_length=20, choices=ResourceType.choices)
    blood_group = models.CharField(max_length=3, blank=True)
    component = models.CharField(max_length=10, blank=True)
    bed_type = models.CharField(max_length=12, blank=True)
    equipment_type = models.CharField(max_length=20, blank=True, choices=EquipmentType.choices)
    capability = models.CharField(max_length=12, blank=True, choices=OrCapability.choices)
    quantity = models.PositiveSmallIntegerField()
    fulfilled = models.PositiveSmallIntegerField(default=0, help_text="Filled in by allocation (#45).")

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="emergencies_item_quantity_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(fulfilled__lte=models.F("quantity")),
                name="emergencies_item_fulfilled_within_quantity",
            ),
        ]

    def __str__(self):
        what = {
            ResourceType.BLOOD: f"{self.blood_group} {self.component}",
            ResourceType.BED: self.bed_type,
            ResourceType.EQUIPMENT: self.equipment_type,
            ResourceType.OPERATING_ROOM: self.capability,
        }[self.resource_type]
        return f"{self.request_id}: {self.quantity} × {what}"
