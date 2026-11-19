from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.resources.models import Resource
from apps.resources.state_machine import StateMachine


class AmbulanceType(models.TextChoices):
    """Story #50: kinds of ambulance the network tracks."""

    BASIC = "basic", "Basic life support"
    ADVANCED = "advanced", "Advanced life support"
    TRANSPORT = "transport", "Patient transport"


class AmbulanceStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    IN_USE = "inUse", "In use"
    MAINTENANCE = "maintenance", "Maintenance"
    OUT_OF_SERVICE = "outOfService", "Out of service"


S = AmbulanceStatus

AMBULANCE_LIFECYCLE = StateMachine(
    "ambulance",
    AmbulanceStatus,
    {
        (S.AVAILABLE, "dispatch"): S.IN_USE,
        (S.IN_USE, "release"): S.AVAILABLE,
        (S.AVAILABLE, "startMaintenance"): S.MAINTENANCE,
        (S.MAINTENANCE, "finishMaintenance"): S.AVAILABLE,
        (S.AVAILABLE, "outOfService"): S.OUT_OF_SERVICE,
        (S.MAINTENANCE, "outOfService"): S.OUT_OF_SERVICE,
        (S.OUT_OF_SERVICE, "returnToService"): S.MAINTENANCE,
    },
)


class TripStatus(models.TextChoices):
    DISPATCHED = "dispatched", "Dispatched"
    EN_ROUTE = "enRoute", "En route"
    ARRIVED = "arrived", "Arrived"
    COMPLETED = "completed", "Completed"


T = TripStatus

TRIP_LIFECYCLE = StateMachine(
    "trip",
    TripStatus,
    {
        (T.DISPATCHED, "startRoute"): T.EN_ROUTE,
        (T.EN_ROUTE, "arrive"): T.ARRIVED,
        (T.ARRIVED, "complete"): T.COMPLETED,
    },
)

ACTIVE_TRIP = (T.DISPATCHED, T.EN_ROUTE, T.ARRIVED)


class AmbulanceQuerySet(models.QuerySet):
    def matchable(self):
        return self.filter(status=AmbulanceStatus.AVAILABLE)


class Ambulance(Resource):
    """One ambulance at a base hospital (story #50)."""

    machine = AMBULANCE_LIFECYCLE
    objects = AmbulanceQuerySet.as_manager()

    identifier = models.CharField(max_length=40, help_text="Call sign, e.g. AMB-12. Unique within a hospital.")
    ambulance_type = models.CharField(max_length=20, choices=AmbulanceType.choices)
    status = models.CharField(
        max_length=20, choices=AmbulanceStatus.choices, default=AmbulanceStatus.AVAILABLE
    )

    class Meta:
        ordering = ["identifier"]
        verbose_name_plural = "ambulances"
        indexes = [models.Index(fields=["ambulance_type", "status"])]
        constraints = [
            models.UniqueConstraint(
                "hospital",
                Lower("identifier"),
                nulls_distinct=False,
                name="ambulance_identifier_unique_per_hospital",
            )
        ]

    def __str__(self):
        return f"{self.identifier} ({self.get_ambulance_type_display()})"


class Trip(models.Model):
    """Simulated ambulance run for one transfer (story #51)."""

    transfer = models.OneToOneField(
        "transfers.Transfer", on_delete=models.PROTECT, related_name="trip"
    )
    ambulance = models.ForeignKey(Ambulance, on_delete=models.PROTECT, related_name="trips")
    status = models.CharField(max_length=12, choices=TripStatus.choices, default=TripStatus.DISPATCHED)
    eta_minutes = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Estimated drive time from supplier to receiver when dispatched."
    )
    dispatched_at = models.DateTimeField(default=timezone.now)
    status_since = models.DateTimeField(default=timezone.now)
    dispatched_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )

    class Meta:
        ordering = ["-dispatched_at", "-id"]
        indexes = [models.Index(fields=["status"], name="trips_status")]

    def __str__(self):
        return f"Trip for transfer #{self.transfer_id}"