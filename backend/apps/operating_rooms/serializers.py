from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import OR_LIFECYCLE, OperatingRoom, OrBooking, OrCapability, OrStatus


class OperatingRoomActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=OR_LIFECYCLE.actions)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class OperatingRoomSerializer(serializers.ModelSerializer):
    """Shape of `OperatingRoom` in frontend/src/api/operatingRooms.ts. POST uses the same fields."""

    capabilities = serializers.ListField(
        child=serializers.ChoiceField(choices=OrCapability.choices), allow_empty=False
    )
    status = serializers.ChoiceField(choices=OrStatus.choices, default=OrStatus.AVAILABLE)
    statusSince = serializers.DateTimeField(source="status_since", read_only=True)
    hospital = serializers.CharField(source="hospital.name", read_only=True, default=None)

    class Meta:
        model = OperatingRoom
        fields = ["id", "name", "capabilities", "location", "status", "statusSince", "hospital"]
        read_only_fields = ["id"]

    def validate_capabilities(self, value):
        """Drop repeats and store the codes sorted, so the same set always looks the same."""
        return sorted(set(value))


MAX_BOOKING_LENGTH = timedelta(hours=24)
START_SLACK = timedelta(minutes=5)  # a start a few minutes ago is still allowed, for clocks that differ


class OrBookingCreateSerializer(serializers.Serializer):
    """POST /api/operating-rooms/bookings/ input (story #29). The room is looked up in the service, so another
    hospital's room answers 404 rather than a validation error."""

    roomId = serializers.IntegerField(min_value=1)
    startsAt = serializers.DateTimeField()
    endsAt = serializers.DateTimeField()
    procedure = serializers.CharField(max_length=120)
    surgeon = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    patientInitials = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")

    def validate(self, data):
        starts, ends = data["startsAt"], data["endsAt"]
        if ends <= starts:
            raise serializers.ValidationError({"endsAt": ["The booking must end after it starts."]})
        if ends - starts > MAX_BOOKING_LENGTH:
            raise serializers.ValidationError({"endsAt": ["A booking can be at most 24 hours long."]})
        if starts < timezone.now() - START_SLACK:
            raise serializers.ValidationError({"startsAt": ["Pick a start time in the future."]})
        return data


class OrBookingSerializer(serializers.ModelSerializer):
    """Shape of an `OrBooking` in frontend/src/api/operatingRooms.ts."""

    roomId = serializers.IntegerField(source="room_id", read_only=True)
    startsAt = serializers.DateTimeField(source="starts_at", read_only=True)
    endsAt = serializers.DateTimeField(source="ends_at", read_only=True)
    patientInitials = serializers.CharField(source="patient_initials", read_only=True)
    bookedBy = serializers.CharField(source="booked_by.get_full_name", read_only=True)
    canCancel = serializers.SerializerMethodField()

    class Meta:
        model = OrBooking
        fields = [
            "id",
            "roomId",
            "startsAt",
            "endsAt",
            "procedure",
            "surgeon",
            "patientInitials",
            "status",
            "bookedBy",
            "canCancel",
        ]

    def get_canCancel(self, booking) -> bool:
        """Whether the requesting user (context["user"]) may cancel it, so the page only offers what works."""
        from .services import may_cancel  # services imports this module

        user = self.context.get("user")
        return bool(user) and booking.status == "booked" and may_cancel(user, booking)
