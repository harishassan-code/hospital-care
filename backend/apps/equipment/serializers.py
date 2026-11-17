from rest_framework import serializers

from .models import EQUIPMENT_LIFECYCLE, Equipment, EquipmentStatus, EquipmentType


class EquipmentActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=EQUIPMENT_LIFECYCLE.actions)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class EquipmentSerializer(serializers.ModelSerializer):
    """Shape of `Equipment` in frontend/src/api/equipment.ts. POST uses the same fields."""

    type = serializers.ChoiceField(source="equipment_type", choices=EquipmentType.choices)
    status = serializers.ChoiceField(choices=EquipmentStatus.choices, default=EquipmentStatus.AVAILABLE)
    statusSince = serializers.DateTimeField(source="status_since", read_only=True)
    hospital = serializers.CharField(source="hospital.name", read_only=True, default=None)

    class Meta:
        model = Equipment
        fields = ["id", "identifier", "type", "name", "location", "status", "statusSince", "hospital"]
        read_only_fields = ["id"]

    def validate_identifier(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Enter the asset tag.")
        return value

    def validate_location(self, value):
        if not value.strip():
            raise serializers.ValidationError("Say where the equipment is kept.")
        return value.strip()
