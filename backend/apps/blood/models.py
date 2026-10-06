from django.db import models
from django.utils import timezone


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


class BloodUnit(models.Model):
    donation_number = models.CharField(
        max_length=30, unique=True, help_text="ISBT 128 donation identification number. Also the API id."
    )
    group = models.CharField(max_length=3, choices=BloodGroup.choices)
    component = models.CharField(max_length=12, choices=Component.choices)
    collected_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=UnitStatus.choices, default=UnitStatus.QUARANTINED)
    location = models.CharField(max_length=100)

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
        if self.status != UnitStatus.ISSUED and self.expires_at <= now:
            return UnitStatus.EXPIRED
        return self.status
