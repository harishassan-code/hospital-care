from datetime import timedelta

from rest_framework import serializers

from .models import BloodUnit, Component

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

    class Meta:
        model = BloodUnit
        fields = ["id", "group", "component", "collectedAt", "expiresAt", "location"]

    def validate_id(self, value):
        if BloodUnit.objects.filter(donation_number=value).exists():
            raise serializers.ValidationError("A unit with this ID already exists.")
        return value

    def validate(self, attrs):
        expires_at = attrs.get("expires_at")
        if expires_at is None:
            attrs["expires_at"] = attrs["collected_at"] + timedelta(days=SHELF_LIFE_DAYS[attrs["component"]])
        elif expires_at <= attrs["collected_at"]:
            raise serializers.ValidationError(
                {"expiresAt": "Expiry date can't be before the collection date."}
            )

        return attrs
