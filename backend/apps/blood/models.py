from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.resources.models import Resource
from apps.resources.state_machine import StateMachine


class BloodGroup(models.TextChoices):
    O_NEG = "O-", "O-"
    O_POS = "O+", "O+"
    A_NEG = "A-", "A-"
    A_POS = "A+", "A+"
    B_NEG = "B-", "B-"
    B_POS = "B+", "B+"
    AB_NEG = "AB-", "AB-"
    AB_POS = "AB+", "AB+"


class Component(models.TextChoices):
    RED_CELLS = "redCells", "Red cells"
    PLASMA = "plasma", "Plasma"
    PLATELETS = "platelets", "Platelets"
    CRYO = "cryo", "Cryo"


class UnitStatus(models.TextChoices):
    QUARANTINED = "quarantined", "Quarantined"
    AVAILABLE = "available", "Available"
    RESERVED = "reserved", "Reserved"
    ISSUED = "issued", "Issued"
    EXPIRED = "expired", "Expired"
    DISCARDED = "discarded", "Discarded"


U = UnitStatus

# Story #18: a unit stays quarantined until every required test passes ("release"), and a failed test
# discards it. Release and discard go through apps.blood.services, which checks the test results.
BLOOD_UNIT_LIFECYCLE = StateMachine(
    "blood unit",
    UnitStatus,
    {
        (U.QUARANTINED, "release"): U.AVAILABLE,  # tests passed
        (U.AVAILABLE, "reserve"): U.RESERVED,
        (U.RESERVED, "cancelReservation"): U.AVAILABLE,
        (U.AVAILABLE, "issue"): U.ISSUED,
        (U.RESERVED, "issue"): U.ISSUED,
        (U.QUARANTINED, "expire"): U.EXPIRED,
        (U.AVAILABLE, "expire"): U.EXPIRED,
        (U.RESERVED, "expire"): U.EXPIRED,
        (U.QUARANTINED, "discard"): U.DISCARDED,  # a test failed
    },
)


class ScreeningTest(models.TextChoices):
    """Mandatory screening for every donated unit (WHO minimum: HIV, hepatitis B and C,
    syphilis; plus malaria, which Pakistan's blood transfusion rules require)."""

    HIV = "hiv", "HIV"
    HBV = "hbv", "Hepatitis B"
    HCV = "hcv", "Hepatitis C"
    SYPHILIS = "syphilis", "Syphilis"
    MALARIA = "malaria", "Malaria"


REQUIRED_TESTS = list(ScreeningTest.values)


def min_donation_interval() -> timedelta:
    return timedelta(days=settings.BLOOD_MIN_DONATION_INTERVAL_DAYS)


class Donor(models.Model):
    """A blood donor (story #20). Demo data uses synthetic identities only, never real people."""

    code = models.CharField(max_length=20, unique=True, help_text="e.g. DNR-00042. Also the API id.")
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, null=True, related_name="+")
    full_name = models.CharField(max_length=150)
    blood_group = models.CharField(max_length=3, choices=BloodGroup.choices)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    # Eligibility screening (story #21). A reason with no end date is a permanent deferral.
    deferral_reason = models.CharField(max_length=300, blank=True)
    deferred_until = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.blood_group})"

    def last_donation_at(self):
        """When this donor last gave blood: the latest collection among their units."""
        latest = self.units.order_by("-collected_at").values_list("collected_at", flat=True).first()
        return latest

    def eligibility(self, on: date | None = None) -> tuple[bool, str, date | None]:
        """(eligible, reason when not, date they become eligible again or None if never/now)."""
        on = on or timezone.localdate()
        if self.deferral_reason and (self.deferred_until is None or self.deferred_until > on):
            return False, self.deferral_reason, self.deferred_until
        last = self.last_donation_at()
        if last is not None:
            next_date = timezone.localdate(last) + min_donation_interval()
            if next_date > on:
                return (
                    False,
                    f"Donated on {timezone.localdate(last):%d %b %Y}; next eligible {next_date:%d %b %Y}.",
                    next_date,
                )
        return True, "", None


class BloodUnit(Resource):
    machine = BLOOD_UNIT_LIFECYCLE

    donation_number = models.CharField(
        max_length=30, unique=True, help_text="ISBT 128 donation identification number. Also the API id."
    )
    group = models.CharField(max_length=3, choices=BloodGroup.choices)
    component = models.CharField(max_length=12, choices=Component.choices)
    collected_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=UnitStatus.choices, default=UnitStatus.QUARANTINED)
    location = models.CharField(max_length=100)
    donor = models.ForeignKey(Donor, on_delete=models.PROTECT, null=True, blank=True, related_name="units")

    class Meta:
        ordering = ["expires_at"]
        indexes = [models.Index(fields=["group", "component", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expires_at__gt=models.F("collected_at")),
                name="blood_unit_expires_after_collection",
            )
        ]

    def __str__(self):
        return f"{self.donation_number} {self.group} {self.get_component_display()}"

    def effective_status(self, now=None) -> str:
        """A unit still on the shelf past its expiry counts as expired, even before anyone updates it."""
        now = now or timezone.now()
        if self.status not in (UnitStatus.ISSUED, UnitStatus.DISCARDED) and self.expires_at <= now:
            return UnitStatus.EXPIRED
        return self.status


class TestResult(models.Model):
    """One screening result for one unit (story #18). Each test is recorded once per unit."""

    __test__ = False  # not a pytest test class, despite the name

    unit = models.ForeignKey(BloodUnit, on_delete=models.CASCADE, related_name="tests")
    test = models.CharField(max_length=12, choices=ScreeningTest.choices)
    passed = models.BooleanField()
    reason = models.CharField(max_length=300, blank=True, help_text="Required when the test failed.")
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )

    class Meta:
        ordering = ["recorded_at"]
        constraints = [models.UniqueConstraint(fields=["unit", "test"], name="blood_test_once_per_unit")]

    def __str__(self):
        return f"{self.unit_id} {self.test}: {'pass' if self.passed else 'FAIL'}"


class AppointmentStatus(models.TextChoices):
    BOOKED = "booked", "Booked"
    CANCELLED = "cancelled", "Cancelled"


class DonationAppointment(models.Model):
    """A donation slot at a hospital's blood bank (story #22). One booked donor per hospital per slot."""

    donor = models.ForeignKey(Donor, on_delete=models.PROTECT, related_name="appointments")
    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, null=True, related_name="+")
    starts_at = models.DateTimeField()
    status = models.CharField(
        max_length=10, choices=AppointmentStatus.choices, default=AppointmentStatus.BOOKED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        constraints = [
            # The database itself refuses a double booking, even if two requests arrive at once.
            models.UniqueConstraint(
                fields=["hospital", "starts_at"],
                condition=models.Q(status="booked"),
                nulls_distinct=False,  # also one booking per slot for staff with no hospital (admins)
                name="blood_one_booking_per_slot",
            )
        ]

    def __str__(self):
        return f"{self.donor_id} at {self.starts_at:%Y-%m-%d %H:%M}"
