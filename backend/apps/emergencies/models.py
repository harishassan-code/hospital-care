from django.conf import settings
from django.db import models
from django.db.models import Case, Value, When

from apps.core import clock
from apps.equipment.models import EquipmentType
from apps.operating_rooms.models import OrCapability
from apps.resources.state_machine import StateMachine


class ErStatus(models.TextChoices):
    ACCEPTING = "accepting", "Accepting patients"
    BUSY = "busy", "Very busy"
    DIVERTING = "diverting", "Not accepting ambulances"


class EmergencyStatus(models.Model):
    """One hospital's emergency department as the public sees it (B19): accepting, very busy or not accepting
    ambulances, the estimated wait and how many are waiting. Updated by that hospital's staff through
    services.update_department_status. A hospital without a row hasn't reported its status."""

    hospital = models.OneToOneField(
        "hospitals.Hospital", on_delete=models.CASCADE, related_name="emergency_status"
    )
    status = models.CharField(max_length=20, choices=ErStatus.choices, default=ErStatus.ACCEPTING)
    wait_minutes = models.PositiveIntegerField(default=0)
    waiting_count = models.PositiveIntegerField(default=0)
    # City time (B21): set on every change by department.update_department_status.
    updated_at = models.DateTimeField(default=clock.now)
    # Who set it last: a person, or the simulation's system user (B21), which leaves a person's change alone
    # for half an hour.
    set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # The factors behind the wait, when the simulation estimated it: [{key, label, value, minutes}].
    factors = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name_plural = "emergency statuses"

    def __str__(self):
        return f"{self.hospital}: {self.get_status_display()}"


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
    created_at = models.DateTimeField(default=clock.now, editable=False)

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
    at = models.DateTimeField(default=clock.now)

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


# ── Patient transfers (B17, stories #63 to #65) ───────────────────────────────────────────────────


class PatientTransferStatus(models.TextChoices):
    REQUESTED = "requested", "Requested"
    ARRIVED = "arrived", "Arrived"
    CANCELLED = "cancelled", "Cancelled"


PT = PatientTransferStatus

# Arrived and cancelled are final. The rules are in patient_transfers.py.
PATIENT_TRANSFER_LIFECYCLE = StateMachine(
    "patient transfer",
    PatientTransferStatus,
    {
        (PT.REQUESTED, "arrive"): PT.ARRIVED,
        (PT.REQUESTED, "cancel"): PT.CANCELLED,
    },
)


class PatientTransferQuerySet(models.QuerySet):
    def with_details(self):
        """What the API shows for a patient transfer, loaded up front: the case and its needs, both hospitals
        and the people who acted. A list of them costs a fixed number of queries."""
        return self.select_related(
            "request", "from_hospital", "to_hospital", "requested_by", "arrived_by"
        ).prefetch_related("request__items")


class PatientTransfer(models.Model):
    """A request to move a case's patient to another hospital (B17), and the case's ownership history: a case
    changes hospital only through an arrived row, so a second table would repeat it. `match` is the
    destination's #42 entry as it stood when the transfer was requested (see labels.hospital_match_data)."""

    request = models.ForeignKey(EmergencyRequest, on_delete=models.PROTECT, related_name="patient_transfers")
    from_hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="+")
    to_hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="+")
    status = models.CharField(
        max_length=10, choices=PatientTransferStatus.choices, default=PatientTransferStatus.REQUESTED
    )
    match = models.JSONField(default=dict, blank=True, help_text="The destination's match when requested.")
    note = models.TextField(blank=True, help_text="Why the patient is being moved.")
    reason = models.TextField(blank=True, help_text="Why the transfer was cancelled.")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    requested_at = models.DateTimeField(default=clock.now)
    arrived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    arrived_at = models.DateTimeField(null=True, blank=True)

    objects = PatientTransferQuerySet.as_manager()

    class Meta:
        ordering = ["-requested_at", "-id"]
        indexes = [
            models.Index(fields=["from_hospital", "status"], name="emergencies_pt_from_status"),
            models.Index(fields=["to_hospital", "status"], name="emergencies_pt_to_status"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(from_hospital=models.F("to_hospital")),
                name="emergencies_pt_distinct_hospitals",
            ),
            # One open request per case: a second one while the first is requested is refused by the database.
            models.UniqueConstraint(
                fields=["request"],
                condition=models.Q(status=PatientTransferStatus.REQUESTED),
                name="emergencies_one_open_patient_transfer",
            ),
        ]

    def __str__(self):
        return f"Patient transfer #{self.pk}"


# ── Emergency department visits (B21) ─────────────────────────────────────────────────────────────


class Triage(models.IntegerChoices):
    """The five-level emergency triage scale: 1 is seen at once, 5 can wait longest."""

    RESUSCITATION = 1, "1 · Resuscitation"
    EMERGENT = 2, "2 · Emergent"
    URGENT = 3, "3 · Urgent"
    LESS_URGENT = 4, "4 · Less urgent"
    NON_URGENT = 5, "5 · Non-urgent"


class AgeBand(models.TextChoices):
    INFANT = "0-4", "0–4"
    CHILD = "5-17", "5–17"
    ADULT = "18-39", "18–39"
    MIDDLE = "40-64", "40–64"
    OLDER = "65+", "65 and over"


class Complaint(models.TextChoices):
    RESPIRATORY = "respiratory", "Breathing"
    CARDIAC = "cardiac", "Chest pain"
    TRAUMA = "trauma", "Injury"
    ABDOMINAL = "abdominal", "Abdominal pain"
    NEUROLOGICAL = "neurological", "Neurological"
    INFECTION = "infection", "Fever or infection"
    OBSTETRIC = "obstetric", "Pregnancy"
    MINOR = "minor", "Minor complaint"


class VisitStatus(models.TextChoices):
    WAITING = "waiting", "Waiting"
    TREATING = "treating", "Being treated"
    BOARDING = "boarding", "Admitted, waiting for a ward bed"
    LEFT = "left", "Left the department"


class VisitOutcome(models.TextChoices):
    DISCHARGED = "discharged", "Discharged home"
    ADMITTED = "admitted", "Admitted to a ward"
    TRANSFERRED = "transferred", "Transferred to another hospital"
    LEFT_UNSEEN = "leftUnseen", "Left without being seen"


VS = VisitStatus

VISIT_LIFECYCLE = StateMachine(
    "visit",
    VisitStatus,
    {
        (VS.WAITING, "startTreatment"): VS.TREATING,
        (VS.WAITING, "leaveUnseen"): VS.LEFT,
        (VS.TREATING, "discharge"): VS.LEFT,
        (VS.TREATING, "transfer"): VS.LEFT,
        (VS.TREATING, "admit"): VS.LEFT,  # a ward bed was free
        (VS.TREATING, "board"): VS.BOARDING,  # admitted, no ward bed yet: keeps the emergency bed
        (VS.BOARDING, "admit"): VS.LEFT,
    },
)


class ErVisit(models.Model):
    """One patient's visit to a hospital's emergency department (B21), from arrival to leaving. Holds the
    least a department needs to run its queue: a random tag, never a name, an age band, the sex, the complaint
    category and the triage level (B23: the minimum necessary). Visits are written by the simulation on
    staging and kept 14 days."""

    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.CASCADE, related_name="er_visits")
    tag = models.CharField(max_length=12, help_text='A random tag for the board, e.g. "ED-4821". Not a name.')
    triage = models.PositiveSmallIntegerField(choices=Triage.choices)
    age_band = models.CharField(max_length=6, choices=AgeBand.choices)
    sex = models.CharField(max_length=1, choices=[("F", "Female"), ("M", "Male")])
    complaint = models.CharField(max_length=14, choices=Complaint.choices)
    status = models.CharField(max_length=10, choices=VisitStatus.choices, default=VisitStatus.WAITING)
    outcome = models.CharField(max_length=12, choices=VisitOutcome.choices, blank=True)
    arrived_at = models.DateTimeField(default=clock.now)
    seen_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)
    # When the current stage is planned to end (treatment), drawn at the start of it.
    due_at = models.DateTimeField(null=True, blank=True)
    bed = models.ForeignKey(
        "hospitals.Bed", on_delete=models.SET_NULL, null=True, blank=True, related_name="er_visits"
    )
    ward_bed = models.ForeignKey(
        "hospitals.Bed", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # The person who last acted on the visit from the queue page (B22): the simulation leaves it to them.
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    machine = VISIT_LIFECYCLE

    class Meta:
        ordering = ["triage", "arrived_at", "id"]
        indexes = [
            models.Index(fields=["hospital", "status"], name="emergencies_visit_hosp_status"),
            models.Index(fields=["hospital", "arrived_at"], name="emergencies_visit_hosp_arrived"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(triage__gte=1, triage__lte=5), name="emergencies_visit_triage"
            ),
        ]

    def __str__(self):
        return f"{self.tag} (triage {self.triage})"
