from django.db import models
from django.utils import timezone


class Ward(models.Model):
    code = models.SlugField(
        max_length=30, unique=True, help_text="Stable id used by the frontend, e.g. 'icu'."
    )
    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=100, help_text="What kind of care the ward gives.")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]

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


class Bed(models.Model):
    """
    One bed. Patient details are deliberately minimal (initials, age, sex) so the board can be
    shown on a ward screen; full patient records belong to a later story.
    """

    label = models.CharField(max_length=20, unique=True, help_text="e.g. ICU-01. Also the bed's API id.")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="beds")
    status = models.CharField(max_length=20, choices=BedStatus.choices, default=BedStatus.FREE)
    status_since = models.DateTimeField(default=timezone.now)

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
