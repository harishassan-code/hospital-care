from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers

from .models import (
    REQUIRED_TESTS,
    BloodUnit,
    Component,
    DonationAppointment,
    Donor,
    ScreeningTest,
    TestResult,
)

# Days each component stays usable, counted from collection. Mirrors COMPONENTS.shelfLifeDays
# in frontend/src/api/blood.ts; keep both in sync.
SHELF_LIFE_DAYS = {
    Component.RED_CELLS: 42,
    Component.PLASMA: 365,
    Component.PLATELETS: 5,
    Component.CRYO: 365,
}


class BloodUnitSerializer(serializers.ModelSerializer):
    """Shape of `BloodUnit` in frontend/src/api/blood.ts."""

    id = serializers.CharField(source="donation_number")
    collectedAt = serializers.DateTimeField(source="collected_at")
    expiresAt = serializers.DateTimeField(source="expires_at")
    status = serializers.SerializerMethodField()

    class Meta:
        model = BloodUnit
        fields = ["id", "group", "component", "collectedAt", "expiresAt", "status", "location"]

    def get_status(self, unit):
        return unit.effective_status(self.context.get("now"))


class BloodUnitCreateSerializer(serializers.ModelSerializer):
    """
    POST /api/blood/units/ (story #17). Expiry defaults from the component's shelf life, so callers only
    send it to override the default (e.g. the lab shortens it after testing).
    """

    id = serializers.CharField(source="donation_number", max_length=30)
    collectedAt = serializers.DateTimeField(source="collected_at")
    expiresAt = serializers.DateTimeField(source="expires_at", required=False)
    donorId = serializers.SlugRelatedField(
        source="donor", slug_field="code", queryset=Donor.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = BloodUnit
        fields = ["id", "group", "component", "collectedAt", "expiresAt", "location", "donorId"]

    def validate_id(self, value):
        if BloodUnit.objects.filter(donation_number=value).exists():
            raise serializers.ValidationError("A unit with this ID already exists.")
        return value

    def validate_collectedAt(self, value):
        if value > timezone.now() + timedelta(minutes=5):  # small allowance for clock differences
            raise serializers.ValidationError("Collection time can't be in the future.")
        return value

    def validate(self, attrs):
        expires_at = attrs.get("expires_at")
        if expires_at is None:
            attrs["expires_at"] = attrs["collected_at"] + timedelta(days=SHELF_LIFE_DAYS[attrs["component"]])
        elif expires_at <= attrs["collected_at"]:
            raise serializers.ValidationError(
                {"expiresAt": "Expiry date can't be before the collection date."}
            )
        donor = attrs.get("donor")
        if donor is not None and donor.blood_group != attrs["group"]:
            raise serializers.ValidationError(
                {"donorId": f"This donor is {donor.blood_group}, but the unit says {attrs['group']}."}
            )

        return attrs


class TestResultSerializer(serializers.ModelSerializer):
    recordedAt = serializers.DateTimeField(source="recorded_at", read_only=True)

    class Meta:
        model = TestResult
        fields = ["test", "passed", "reason", "recordedAt"]


class BloodUnitDetailSerializer(BloodUnitSerializer):
    """GET /api/blood/units/<id>/: the unit plus its donor and screening results (story #18, #20)."""

    donorId = serializers.SlugRelatedField(source="donor", slug_field="code", read_only=True)
    tests = TestResultSerializer(many=True, read_only=True)
    missingTests = serializers.SerializerMethodField()

    class Meta(BloodUnitSerializer.Meta):
        fields = [*BloodUnitSerializer.Meta.fields, "donorId", "tests", "missingTests"]

    def get_missingTests(self, unit):
        passed = {t.test for t in unit.tests.all() if t.passed}
        return [test for test in REQUIRED_TESTS if test not in passed]


class RecordTestSerializer(serializers.Serializer):
    test = serializers.ChoiceField(choices=ScreeningTest.choices)
    passed = serializers.BooleanField()
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs["passed"] and not attrs["reason"].strip():
            raise serializers.ValidationError({"reason": "Say why the test failed."})
        return attrs


class UnitActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=BloodUnit.machine.actions)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class DonorSerializer(serializers.ModelSerializer):
    """Shape of a donor in the API (stories #20, #21). Eligibility is worked out on read."""

    id = serializers.CharField(source="code", read_only=True)
    fullName = serializers.CharField(source="full_name", max_length=150)
    bloodGroup = serializers.ChoiceField(
        source="blood_group", choices=Donor._meta.get_field("blood_group").choices
    )
    phone = serializers.RegexField(r"^\+?[\d\s-]{7,20}$", required=False, allow_blank=True)
    lastDonationAt = serializers.SerializerMethodField()
    eligible = serializers.SerializerMethodField()
    ineligibleReason = serializers.SerializerMethodField()
    eligibleFrom = serializers.SerializerMethodField()

    class Meta:
        model = Donor
        fields = [
            "id", "fullName", "bloodGroup", "phone", "email",
            "lastDonationAt", "eligible", "ineligibleReason", "eligibleFrom",
        ]  # fmt: skip

    def _eligibility(self, donor):
        cache = self.context.setdefault("_eligibility", {})
        if donor.pk not in cache:
            cache[donor.pk] = donor.eligibility()
        return cache[donor.pk]

    def get_lastDonationAt(self, donor):
        last = donor.last_donation_at()
        return last.isoformat() if last else None

    def get_eligible(self, donor):
        return self._eligibility(donor)[0]

    def get_ineligibleReason(self, donor):
        return self._eligibility(donor)[1]

    def get_eligibleFrom(self, donor):
        when = self._eligibility(donor)[2]
        return when.isoformat() if when else None


class ScreeningSerializer(serializers.Serializer):
    eligible = serializers.BooleanField()
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")
    deferredUntil = serializers.DateField(required=False, allow_null=True, default=None)

    def validate_deferredUntil(self, value):
        if value is not None and value <= timezone.localdate():
            raise serializers.ValidationError(
                "The deferral must end in the future (or leave it empty for permanent)."
            )
        return value


class AppointmentSerializer(serializers.ModelSerializer):
    donorId = serializers.SlugRelatedField(source="donor", slug_field="code", queryset=Donor.objects.all())
    donorName = serializers.CharField(source="donor.full_name", read_only=True)
    startsAt = serializers.DateTimeField(source="starts_at")
    slotMinutes = serializers.SerializerMethodField()

    class Meta:
        model = DonationAppointment
        fields = ["id", "donorId", "donorName", "startsAt", "slotMinutes", "status"]
        read_only_fields = ["id", "status"]

    def get_slotMinutes(self, appointment):
        return settings.BLOOD_APPOINTMENT_SLOT_MINUTES
