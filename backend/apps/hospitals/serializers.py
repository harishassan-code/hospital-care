from django.db.models import Count
from rest_framework import serializers

from apps.accounts.serializers import PHONE_REGEX

from .models import Bed, Capability, Department, DoctorShift, Hospital, StorageLocation, Ward
from .services import ACTIONS, new_ward_code


class WardSerializer(serializers.ModelSerializer):
    id = serializers.CharField(source="code")

    class Meta:
        model = Ward
        fields = ["id", "name", "kind"]


class BedSerializer(serializers.ModelSerializer):
    """Shape of `Bed` in frontend/src/api/beds.ts. Patient fields are left out when the bed is empty."""

    id = serializers.CharField(source="label")
    ward = serializers.CharField(source="ward.code")
    type = serializers.CharField(source="bed_type")
    statusSince = serializers.DateTimeField(source="status_since")

    class Meta:
        model = Bed
        fields = ["id", "ward", "label", "type", "status", "statusSince"]

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


# ── Hospital network (docs/architecture/api-contracts.md) ────────────────────


class HospitalSerializer(serializers.ModelSerializer):
    latitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, min_value=-90, max_value=90, coerce_to_string=False
    )
    longitude = serializers.DecimalField(
        max_digits=9, decimal_places=6, min_value=-180, max_value=180, coerce_to_string=False
    )
    phone = serializers.RegexField(PHONE_REGEX, required=False, allow_blank=True, max_length=20)
    isActive = serializers.BooleanField(source="is_active", required=False)
    capabilities = serializers.SlugRelatedField(
        slug_field="code", many=True, required=False, queryset=Capability.objects.all()
    )

    class Meta:
        model = Hospital
        fields = [
            "id",
            "name",
            "type",
            "address",
            "latitude",
            "longitude",
            "phone",
            "isActive",
            "capabilities",
        ]

    def validate_name(self, value):
        value = value.strip()
        taken = Hospital.objects.filter(name__iexact=value)
        if self.instance:
            taken = taken.exclude(pk=self.instance.pk)
        if taken.exists():
            raise serializers.ValidationError("A hospital with this name is already registered.")
        return value

    def validate_address(self, value):
        return value.strip()


class UniqueNameInHospital:
    """Departments, wards and locations: the name is unique within one hospital (context["hospital"])."""

    def validate_name(self, value):
        value = value.strip()
        if self.Meta.model.objects.filter(hospital=self.context["hospital"], name__iexact=value).exists():
            raise serializers.ValidationError("This hospital already has one with that name.")
        return value


class DepartmentSerializer(UniqueNameInHospital, serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name"]


class LocationSerializer(UniqueNameInHospital, serializers.ModelSerializer):
    class Meta:
        model = StorageLocation
        fields = ["id", "name"]


class WardItemSerializer(UniqueNameInHospital, serializers.ModelSerializer):
    departmentId = serializers.PrimaryKeyRelatedField(
        source="department", queryset=Department.objects.all(), allow_null=True, required=False
    )
    bedCount = serializers.SerializerMethodField()

    class Meta:
        model = Ward
        fields = ["id", "code", "name", "kind", "departmentId", "bedCount"]
        read_only_fields = ["code"]

    def get_bedCount(self, ward):
        # Lists annotate bed_count in one query; a single new ward counts its own.
        return ward.bed_count if hasattr(ward, "bed_count") else ward.beds.count()

    def validate_departmentId(self, department):
        if department and department.hospital_id != self.context["hospital"].pk:
            raise serializers.ValidationError("Choose a department of this hospital.")
        return department

    def create(self, validated_data):
        validated_data["code"] = new_ward_code(validated_data["hospital"], validated_data["name"])
        return super().create(validated_data)


class HospitalDetailSerializer(HospitalSerializer):
    departments = DepartmentSerializer(many=True, read_only=True)
    wards = serializers.SerializerMethodField()
    locations = LocationSerializer(many=True, read_only=True)

    class Meta(HospitalSerializer.Meta):
        fields = [*HospitalSerializer.Meta.fields, "departments", "wards", "locations"]

    def get_wards(self, hospital):
        wards = hospital.wards.annotate(bed_count=Count("beds"))
        return WardItemSerializer(wards, many=True).data


class CapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Capability
        fields = ["code", "name"]
