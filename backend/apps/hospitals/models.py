from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from apps.resources.models import Resource
from apps.resources.state_machine import StateMachine


class HospitalType(models.TextChoices):
    HOSPITAL = "hospital", "Hospital"
    BLOOD_BANK = "bloodBank", "Blood bank"


class Capability(models.Model):
    """The managed list of things a hospital can offer, e.g. trauma centre, NICU. Edited in Django admin."""

    code = models.SlugField(max_length=30, unique=True, help_text="Stable id used by the frontend.")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "capabilities"

    def __str__(self):
        return self.name


class Hospital(models.Model):
    """A hospital or blood bank in the network. Never deleted: deactivate it, and matching leaves it out."""

    name = models.CharField(max_length=150)
    type = models.CharField(max_length=20, choices=HospitalType.choices, default=HospitalType.HOSPITAL)
    address = models.CharField(max_length=300)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)]
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)]
    )
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    capabilities = models.ManyToManyField(Capability, blank=True, related_name="hospitals")

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="hospitals_hospital_name_ci_unique")]

    def __str__(self):
        return self.name


class Department(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name="departments")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint("hospital", Lower("name"), name="hospitals_department_name_unique")
        ]

    def __str__(self):
        return f"{self.name} ({self.hospital})"


class StorageLocation(models.Model):
    """A place resources are kept, e.g. "Blood fridge 1". Resources point here through storage_location."""

    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name="locations")
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint("hospital", Lower("name"), name="hospitals_location_name_unique")
        ]

    def __str__(self):
        return f"{self.name} ({self.hospital})"


class Ward(models.Model):
    code = models.SlugField(
        max_length=30, unique=True, help_text="Stable id used by the frontend, e.g. 'icu'."
    )
    # Nullable only for wards created before Sprint 2; seed_demo backfills them. The API always sets it.
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, null=True, blank=True, related_name="wards"
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="wards"
    )
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=100, help_text="What kind of care the ward gives.")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [models.UniqueConstraint("hospital", Lower("name"), name="hospitals_ward_name_unique")]

    def __str__(self):
        return self.name


class BedStatus(models.TextChoices):
    OCCUPIED = "occupied", "Occupied"
    RESERVED = "reserved", "Reserved"
    CLEANING = "cleaning", "Cleaning"
    FREE = "free", "Free"
    OUT_OF_SERVICE = "outOfService", "Out of service"


class Isolation(models.TextChoices):
    CONTACT = "contact", "Contact precautions"
    DROPLET = "droplet", "Droplet precautions"
    AIRBORNE = "airborne", "Airborne precautions"


class Sex(models.TextChoices):
    FEMALE = "F", "Female"
    MALE = "M", "Male"


S = BedStatus

BED_LIFECYCLE = StateMachine(
    "bed",
    BedStatus,
    {
        (S.OCCUPIED, "discharge"): S.CLEANING,
        (S.CLEANING, "markReady"): S.FREE,
        (S.FREE, "reserve"): S.RESERVED,
        (S.FREE, "outOfService"): S.OUT_OF_SERVICE,
        (S.RESERVED, "cancelReservation"): S.FREE,
        (S.OUT_OF_SERVICE, "returnToService"): S.CLEANING,
    },
)


class Bed(Resource):
    """
    One bed. Patient details are deliberately minimal (initials, age, sex) so the board can be
    shown on a ward screen; full patient records belong to a later story.
    The bed's hospital is always its ward's hospital (set in save()).
    """

    machine = BED_LIFECYCLE

    label = models.CharField(max_length=20, unique=True, help_text="e.g. ICU-01. Also the bed's API id.")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="beds")
    status = models.CharField(max_length=20, choices=BedStatus.choices, default=BedStatus.FREE)

    patient_initials = models.CharField(max_length=10, blank=True)
    patient_age = models.PositiveSmallIntegerField(null=True, blank=True)
    patient_sex = models.CharField(max_length=1, choices=Sex.choices, blank=True)
    admitted_at = models.DateTimeField(null=True, blank=True)
    expected_discharge = models.DateField(null=True, blank=True)
    isolation = models.CharField(max_length=10, choices=Isolation.choices, blank=True)

    class Meta:
        ordering = ["ward__sort_order", "label"]
        indexes = [models.Index(fields=["status"])]

    def __str__(self):
        return self.label

    def save(self, *args, **kwargs):
        self.hospital_id = self.ward.hospital_id
        super().save(*args, **kwargs)

    def clear_patient(self):
        self.patient_initials = ""
        self.patient_age = None
        self.patient_sex = ""
        self.admitted_at = None
        self.expected_discharge = None
        self.isolation = ""


class DoctorShift(models.Model):
    """A doctor's regular daily shift, shown on the public landing page."""

    name = models.CharField(max_length=150)
    department = models.CharField(max_length=100)
    start = models.TimeField()
    end = models.TimeField(help_text="Earlier than start means the shift runs past midnight.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["department", "start", "name"]

    def __str__(self):
        return f"{self.name} ({self.department})"
