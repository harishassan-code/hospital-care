from rest_framework import serializers

from .models import AMBULANCE_LIFECYCLE, TRIP_LIFECYCLE, Ambulance, AmbulanceStatus, AmbulanceType, Trip


class AmbulanceSerializer(serializers.ModelSerializer):
    type = serializers.ChoiceField(source="ambulance_type", choices=AmbulanceType.choices)
    status = serializers.ChoiceField(choices=AmbulanceStatus.choices, default=AmbulanceStatus.AVAILABLE)
    statusSince = serializers.DateTimeField(source="status_since", read_only=True)
    hospital = serializers.CharField(source="hospital.name", read_only=True, default=None)

    class Meta:
        model = Ambulance
        fields = ["id", "identifier", "type", "status", "statusSince", "hospital"]
        read_only_fields = ["id"]

    def validate_identifier(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Enter the call sign.")
        return value


class DispatchTripSerializer(serializers.Serializer):
    ambulanceId = serializers.IntegerField()


class TripActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=TRIP_LIFECYCLE.actions)


def trip_payload(trip: Trip, *, user) -> dict:
    from .services import trip_actions_for

    ambulance = trip.ambulance
    return {
        "id": trip.pk,
        "status": trip.status,
        "etaMinutes": trip.eta_minutes,
        "dispatchedAt": serializers.DateTimeField().to_representation(trip.dispatched_at),
        "ambulance": {
            "id": ambulance.pk,
            "identifier": ambulance.identifier,
            "type": ambulance.ambulance_type,
        },
        "actions": trip_actions_for(user, trip),
    }


class AmbulanceActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=AMBULANCE_LIFECYCLE.actions)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")