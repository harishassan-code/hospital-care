from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.resources.models import Resource
from apps.resources.state_machine import StateMachine


class AmbulanceType(models.TextChoices):
    """Life support level of the vehicle (story #50)."""

    BASIC = "basic", "Basic life support"
    ADVANCED = "advanced", "Advanced life support"
    PATIENT_TRANSPORT = "patientTransport", "Patient transport"


class AmbulanceStatus(models.TextChoices):
    AVAILABLE = "available", "Available"
    DISPATCHED = "dispatched", "On trip"
    MAINTENANCE = "maintenance", "In maintenance"
    OUT_OF_SERVICE = "outOfService", "Out of service"


S = AmbulanceStatus

# Status changes by hand go through POST /api/ambulances/<id>/actions/. `dispatch` and `release` are the
# trip's moves (story #51): the manual endpoint refuses them, see TRIP_ONLY_ACTIONS.
AMBULANCE_LIFECYCLE = StateMachine(
    "vehicle",  # for the 409 message: "Can't outOfService a vehicle that is out of service."
    AmbulanceStatus,
    {
        (S.AVAILABLE, "startMaintenance"): S.MAINTENANCE,
        (S.MAINTENANCE, "finishMaintenance"): S.AVAILABLE,
        (S.AVAILABLE, "outOfService"): S.OUT_OF_SERVICE,
        (S.MAINTENANCE, "outOfService"): S.OUT_OF_SERVICE,
        (S.OUT_OF_SERVICE, "returnToService"): S.MAINTENANCE,
        (S.AVAILABLE, "dispatch"): S.DISPATCHED,
        (S.DISPATCHED, "release"): S.AVAILABLE,
    },
)
TRIP_ONLY_ACTIONS = ("dispatch", "release")


class Ambulance(Resource):
    """One ambulance at its base hospital, e.g. AMB-04, advanced life support (story #50)."""

    machine = AMBULANCE_LIFECYCLE

    identifier = models.CharField(
        max_length=40, help_text="Asset tag, e.g. AMB-04. Unique within a hospital."
    )
    type = models.CharField(max_length=20, choices=AmbulanceType.choices)
    status = models.CharField(
        max_length=20, choices=AmbulanceStatus.choices, default=AmbulanceStatus.AVAILABLE
    )

    class Meta:
        ordering = ["type", "identifier"]
        indexes = [models.Index(fields=["type", "status"])]
        constraints = [
            models.UniqueConstraint(
                "hospital",
                Lower("identifier"),
                nulls_distinct=False,  # unique for network-level (no hospital) rows too
                name="ambulance_identifier_unique_per_hospital",
            )
        ]

    def __str__(self):
        return f"{self.identifier} ({self.get_type_display()})"


class TripStatus(models.TextChoices):
    DISPATCHED = "dispatched", "Dispatched"
    EN_ROUTE = "enRoute", "En route"
    ARRIVED = "arrived", "Arrived"
    COMPLETED = "completed", "Completed"


T = TripStatus
# A trip that is still on the road: its transfer and its ambulance are tied up (story #51).
TRIP_ACTIVE = (T.DISPATCHED, T.EN_ROUTE, T.ARRIVED)

TRIP_LIFECYCLE = StateMachine(
    "trip",
    TripStatus,
    {
        (T.DISPATCHED, "depart"): T.EN_ROUTE,
        (T.EN_ROUTE, "arrive"): T.ARRIVED,
        (T.ARRIVED, "complete"): T.COMPLETED,
    },
)


class Trip(models.Model):
    """One ambulance carrying one approved transfer from its supplier to its receiver (story #51). The ETA is
    stored once, at dispatch. Completing a trip frees the ambulance; the receiver still confirms receipt."""

    transfer = models.ForeignKey("transfers.Transfer", on_delete=models.PROTECT, related_name="trips")
    ambulance = models.ForeignKey(Ambulance, on_delete=models.PROTECT, related_name="trips")
    status = models.CharField(max_length=12, choices=TripStatus.choices, default=TripStatus.DISPATCHED)
    eta_minutes = models.PositiveSmallIntegerField(help_text="Estimated minutes, set at dispatch.")
    dispatched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    dispatched_at = models.DateTimeField(default=timezone.now)
    departed_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-dispatched_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["transfer"],
                condition=Q(status__in=TRIP_ACTIVE),
                name="trip_one_active_per_transfer",
            ),
            models.UniqueConstraint(
                fields=["ambulance"],
                condition=Q(status__in=TRIP_ACTIVE),
                name="trip_one_active_per_ambulance",
            ),
        ]

    def __str__(self):
        return f"Trip #{self.pk}"
