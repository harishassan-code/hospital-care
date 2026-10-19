from rest_framework import serializers

from .models import BloodUnit


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
