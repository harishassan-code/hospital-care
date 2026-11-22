"""Specialists in the API (B16, stories #61 and #62). The shapes are in frontend/src/api/specialists.ts."""

from rest_framework import serializers

from apps.hospitals.models import Hospital

from .models import OnCallWindow, Specialist
from .services import window_covering


class SpecialistInputSerializer(serializers.Serializer):
    """POST /api/specialists/: all three fields are required. `hospitalId` must be an active hospital, and the
    validated value is the hospital itself."""

    name = serializers.CharField(max_length=150)
    specialty = serializers.CharField(max_length=100)
    hospitalId = serializers.IntegerField(min_value=1)

    def validate_hospitalId(self, value):
        hospital = Hospital.objects.filter(pk=value, is_active=True).first()
        if hospital is None:
            raise serializers.ValidationError("No active hospital with that id.")
        return hospital


class SpecialistUpdateSerializer(serializers.Serializer):
    """PATCH /api/specialists/<id>/: any of the three. The hospital can't change (see the contracts doc)."""

    name = serializers.CharField(max_length=150, required=False)
    specialty = serializers.CharField(max_length=100, required=False)
    isActive = serializers.BooleanField(required=False)


class OnCallWindowInputSerializer(serializers.Serializer):
    """POST /api/specialists/<id>/on-call/: both times with their offset, e.g. "2030-01-15T20:00+05:00"."""

    startsAt = serializers.DateTimeField()
    endsAt = serializers.DateTimeField()


class SpecialistQuerySerializer(serializers.Serializer):
    """GET /api/specialists/?hospital=&specialty=&availableNow=: every filter is optional."""

    hospital = serializers.IntegerField(required=False, min_value=1)
    specialty = serializers.CharField(max_length=100, required=False, allow_blank=True)
    availableNow = serializers.BooleanField(required=False, default=False)


class OnCallWindowSerializer(serializers.ModelSerializer):
    startsAt = serializers.DateTimeField(source="starts_at", read_only=True)
    endsAt = serializers.DateTimeField(source="ends_at", read_only=True)

    class Meta:
        model = OnCallWindow
        fields = ["id", "startsAt", "endsAt"]


class SpecialistSerializer(serializers.ModelSerializer):
    """One specialist as the list shows it. Needs `context["now"]` (the request's time) for the on-call
    fields, and a queryset from `Specialist.objects.with_schedule(now)`."""

    isActive = serializers.BooleanField(source="is_active", read_only=True)
    hospital = serializers.SerializerMethodField()
    onCallNow = serializers.SerializerMethodField()
    onCallUntil = serializers.SerializerMethodField()

    class Meta:
        model = Specialist
        fields = ["id", "name", "specialty", "isActive", "hospital", "onCallNow", "onCallUntil"]

    def get_hospital(self, specialist) -> dict:
        return {"id": specialist.hospital_id, "name": specialist.hospital.name}

    def _covering(self, specialist) -> OnCallWindow | None:
        """A deactivated specialist is never on call, even inside a window."""
        return window_covering(specialist, self.context["now"]) if specialist.is_active else None

    def get_onCallNow(self, specialist) -> bool:
        return self._covering(specialist) is not None

    def get_onCallUntil(self, specialist) -> str | None:
        window = self._covering(specialist)
        return None if window is None else serializers.DateTimeField().to_representation(window.ends_at)


class SpecialistDetailSerializer(SpecialistSerializer):
    """One specialist with the windows that haven't ended yet, by start."""

    onCall = serializers.SerializerMethodField()

    class Meta(SpecialistSerializer.Meta):
        fields = [*SpecialistSerializer.Meta.fields, "onCall"]

    def get_onCall(self, specialist) -> list:
        return OnCallWindowSerializer(specialist.upcoming_windows, many=True).data
