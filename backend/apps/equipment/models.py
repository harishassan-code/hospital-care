from django.db import models
from django.db.models.functions import Lower

from apps.resources.models import Resource
from apps.resources.state_machine import StateMachine


class EquipmentType(models.TextChoices):
    """Critical equipment worth sharing across the network (story #26)."""

    VENTILATOR = "ventilator", "Ventilator"
    MONITOR = "monitor", "Patient monitor"
    DEFIBRILLATOR = "defibrillator", "Defibrillator"
    DIALYSIS = "dialysis", "Dialysis machine"


class EquipmentStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    IN_USE = "inUse", "In use"
    MAINTENANCE = "maintenance", "Maintenance"
    OUT_OF_SERVICE = "outOfService", "Out of service"


S = EquipmentStatus

# Status changes after registration are story #27 (Equipment operational status), which adds the API.
EQUIPMENT_LIFECYCLE = StateMachine(
    "equipment",
    EquipmentStatus,
    {
        (S.AVAILABLE, "use"): S.IN_USE,
        (S.IN_USE, "release"): S.AVAILABLE,
        (S.AVAILABLE, "startMaintenance"): S.MAINTENANCE,
        (S.IN_USE, "startMaintenance"): S.MAINTENANCE,
        (S.MAINTENANCE, "finishMaintenance"): S.AVAILABLE,
        (S.AVAILABLE, "outOfService"): S.OUT_OF_SERVICE,
        (S.MAINTENANCE, "outOfService"): S.OUT_OF_SERVICE,
        (S.OUT_OF_SERVICE, "returnToService"): S.MAINTENANCE,
    },
)


class Equipment(Resource):
    """One piece of critical equipment, e.g. ventilator VENT-003 in ICU bay 2 (story #26)."""

    machine = EQUIPMENT_LIFECYCLE

    identifier = models.CharField(
        max_length=40, help_text="Asset tag, e.g. VENT-003. Unique within a hospital."
    )
    equipment_type = models.CharField(max_length=20, choices=EquipmentType.choices)
    name = models.CharField(max_length=120, blank=True, help_text="Make and model, e.g. Dräger Evita V500.")
    location = models.CharField(max_length=120, help_text="Where to find it, e.g. ICU bay 2.")
    status = models.CharField(
        max_length=20, choices=EquipmentStatus.choices, default=EquipmentStatus.AVAILABLE
    )

    class Meta:
        ordering = ["equipment_type", "identifier"]
        verbose_name_plural = "equipment"
        indexes = [models.Index(fields=["equipment_type", "status"])]
        constraints = [
            models.UniqueConstraint(
                "hospital",
                Lower("identifier"),
                nulls_distinct=False,  # unique for network-level (no hospital) rows too
                name="equipment_identifier_unique_per_hospital",
            )
        ]

    def __str__(self):
        return f"{self.identifier} ({self.get_equipment_type_display()})"
