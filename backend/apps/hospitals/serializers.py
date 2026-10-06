from rest_framework import serializers

from .models import Bed, DoctorShift, Ward
from .services import ACTIONS


class WardSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="code")

    class Meta:
        model = Ward
        fields = ["id", "name", "kind"]


class BedSerializer(serializers.ModelSerializer):
    """Shape of `Bed` in frontend/src/api/beds.ts. Patient fields are left out when the bed is empty."""

    id = serializers.CharField(source="label")
    ward = serializers.CharField(source="ward.code")
    statusSince = serializers.DateTimeField(source="status_since")

    class Meta:
        model = Bed
        fields = ["id", "ward", "label", "status", "statusSince"]

    def to_representation(self, bed):
        data = super().to_representation(bed)
        if bed.patient_initials:
            data["patient"] = {
                "initials": bed.patient_initials,
                "age": bed.patient_age,
                "sex": bed.patient_sex,
            }
        if bed.admitted_at:
            data["admittedAt"] = serializers.DateTimeField().to_representation(bed.admitted_at)
        if bed.expected_discharge:
            data["expectedDischarge"] = bed.expected_discharge.isoformat()
        if bed.isolation:
            data["isolation"] = bed.isolation
        return data


class BedActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=ACTIONS)


class DoctorSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()
    start = serializers.TimeField(format="%H:%M")
    end = serializers.TimeField(format="%H:%M")

    class Meta:
        model = DoctorShift
        fields = ["id", "name", "department", "start", "end"]

    def get_id(self, shift):
        return f"d{shift.pk:02d}"
