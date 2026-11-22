from rest_framework import serializers

from apps.hospitals.models import Hospital

from .models import AMBULANCE_LIFECYCLE, TRIP_ACTIVE, Ambulance, AmbulanceType, Trip
from .services import trip_actions_for

MAX_NOTE = 300


class AmbulanceActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=AMBULANCE_LIFECYCLE.actions)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class AmbulanceSerializer(serializers.ModelSerializer):
    """Shape of `Ambulance` in frontend/src/api/ambulances.ts. POST takes identifier, type and hospitalId."""

    type = serializers.ChoiceField(choices=AmbulanceType.choices)
    status = serializers.CharField(read_only=True)
    statusSince = serializers.DateTimeField(source="status_since", read_only=True)
    hospitalId = serializers.PrimaryKeyRelatedField(
        source="hospital", queryset=Hospital.objects.filter(is_active=True), write_only=True, required=False
    )
    hospital = serializers.CharField(source="hospital.name", read_only=True, default=None)
    trip = serializers.SerializerMethodField()

    class Meta:
        model = Ambulance
        fields = ["id", "identifier", "type", "status", "statusSince", "hospitalId", "hospital", "trip"]
        read_only_fields = ["id"]

    def validate_identifier(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Enter the asset tag.")
        return value

    def get_trip(self, ambulance):
        """The trip on the road with this ambulance, or null. The list prefetches it as `active_trips`."""
        trips = getattr(ambulance, "active_trips", None)
        if trips is None:
            trips = list(ambulance.trips.filter(status__in=TRIP_ACTIVE)[:1])
        if not trips:
            return None
        trip = trips[0]
        return {"id": trip.pk, "status": trip.status, "transferId": trip.transfer_id}


class TripDispatchSerializer(serializers.Serializer):
    """POST /api/transfers/<id>/trips/: the ambulance to send."""

    ambulance = serializers.IntegerField()


class TripActionSerializer(serializers.Serializer):
    """POST /api/trips/<id>/actions/: one step, with an optional note. An unknown step is refused as a
    conflict."""

    action = serializers.CharField(max_length=20)
    note = serializers.CharField(max_length=MAX_NOTE, required=False, allow_blank=True, default="")


class TripSerializer(serializers.Serializer):
    """One trip (story #51). Shape of `Trip` in frontend/src/api/trips.ts. The trip needs `transfer`,
    `ambulance` and `dispatched_by` loaded. `self.context["user"]` decides `actions`."""

    def to_representation(self, trip: Trip):
        user = self.context.get("user")
        dispatcher = trip.dispatched_by
        ambulance = trip.ambulance
        return {
            "id": trip.pk,
            "transferId": trip.transfer_id,
            "status": trip.status,
            "ambulance": {"id": ambulance.pk, "identifier": ambulance.identifier, "type": ambulance.type},
            "etaMinutes": trip.eta_minutes,
            "dispatchedBy": dispatcher.get_full_name() or dispatcher.email,
            "dispatchedAt": serializers.DateTimeField().to_representation(trip.dispatched_at),
            "departedAt": _stamp(trip.departed_at),
            "arrivedAt": _stamp(trip.arrived_at),
            "completedAt": _stamp(trip.completed_at),
            "actions": trip_actions_for(user, trip) if user is not None else [],
        }


def _stamp(value):
    return serializers.DateTimeField().to_representation(value) if value else None
