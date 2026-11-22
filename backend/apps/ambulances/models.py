from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.resources.state_machine import StateMachine


class AmbulanceType(models.TextChoices):
    """Story #50."""

    BLS = "bls", "Basic life support"
    ALS = "als", "Advanced life support"
    PTS = "pts", "Patient transport"


class AmbulanceStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    ON_TRIP = "onTrip", "On trip"
    MAINTENANCE = "maintenance", "Maintenance"
    OUT_OF_SERVICE = "outOfService", "Out of service"


A = AmbulanceStatus

# startTrip and endTrip are made only by a trip (story #51); MANUAL_ACTIONS are what staff can do by hand.
AMBULANCE_LIFECYCLE = StateMachine(
    "ambulance",
    AmbulanceStatus,
    {
        (A.AVAILABLE, "startTrip"): A.ON_TRIP,
        (A.ON_TRIP, "endTrip"): A.AVAILABLE,
        (A.AVAILABLE, "startMaintenance"): A.MAINTENANCE,
        (A.MAINTENANCE, "finishMaintenance"): A.AVAILABLE,
        (A.AVAILABLE, "outOfService"): A.OUT_OF_SERVICE,
        (A.MAINTENANCE, "outOfService"): A.OUT_OF_SERVICE,
        (A.OUT_OF_SERVICE, "returnToService"): A.MAINTENANCE,
    },
)
MANUAL_ACTIONS = [a for a in AMBULANCE_LIFECYCLE.actions if a not in ("startTrip", "endTrip")]


class Ambulance(models.Model):
    """One vehicle in a hospital's fleet, e.g. AMB-CG-01 (story #50)."""

    machine = AMBULANCE_LIFECYCLE

    hospital = models.ForeignKey("hospitals.Hospital", on_delete=models.PROTECT, related_name="ambulances")
    identifier = models.CharField(max_length=40, help_text="Fleet number, e.g. AMB-CG-01.")
    ambulance_type = models.CharField(max_length=10, choices=AmbulanceType.choices)
    plate = models.CharField(max_length=20, blank=True)
    note = models.CharField(max_length=200, blank=True)
    status = models.CharField(
        max_length=20, choices=AmbulanceStatus.choices, default=AmbulanceStatus.AVAILABLE
    )
    status_since = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["hospital_id", "identifier"]
        constraints = [
            models.UniqueConstraint(Lower("identifier"), name="ambulance_identifier_unique"),
        ]

    def __str__(self):
        return f"{self.identifier} ({self.get_ambulance_type_display()})"


class TripStatus(models.TextChoices):
    DISPATCHED = "dispatched", "Dispatched"
    EN_ROUTE = "enRoute", "En route"
    ARRIVED = "arrived", "Arrived"
    COMPLETED = "completed", "Completed"
    CANCELLED = "cancelled", "Cancelled"


T = TripStatus

# Story #51. Simulated by buttons: staff mark en route and arrived; receipt completes, cancel cancels.
TRIP_LIFECYCLE = StateMachine(
    "trip",
    TripStatus,
    {
        (T.DISPATCHED, "enRoute"): T.EN_ROUTE,
        (T.EN_ROUTE, "arrive"): T.ARRIVED,
        (T.DISPATCHED, "complete"): T.COMPLETED,
        (T.EN_ROUTE, "complete"): T.COMPLETED,
        (T.ARRIVED, "complete"): T.COMPLETED,
        (T.DISPATCHED, "cancel"): T.CANCELLED,
        (T.EN_ROUTE, "cancel"): T.CANCELLED,
        (T.ARRIVED, "cancel"): T.CANCELLED,
    },
)
OPEN_TRIP = (T.DISPATCHED, T.EN_ROUTE, T.ARRIVED)


class Trip(models.Model):
    """One ambulance carrying one transfer (story #51)."""

    ambulance = models.ForeignKey(Ambulance, on_delete=models.PROTECT, related_name="trips")
    transfer = models.OneToOneField("transfers.Transfer", on_delete=models.CASCADE, related_name="trip")
    status = models.CharField(max_length=12, choices=TripStatus.choices, default=TripStatus.DISPATCHED)
    eta_minutes = models.PositiveIntegerField(null=True, blank=True)
    dispatched_at = models.DateTimeField(default=timezone.now)
    en_route_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-dispatched_at", "-id"]

    def __str__(self):
        return f"Trip #{self.pk} {self.ambulance.identifier}"
