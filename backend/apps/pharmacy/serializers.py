from rest_framework import serializers

from .models import Batch, Medicine


class BatchSerializer(serializers.ModelSerializer):
    expiresOn = serializers.DateField(source="expires_on")

    class Meta:
        model = Batch
        fields = ["number", "expiresOn", "quantity"]


class MedicineSerializer(serializers.ModelSerializer):
    """Shape of `Medicine` in frontend/src/api/pharmacy.ts."""

    id = serializers.CharField(source="code")
    reorderLevel = serializers.IntegerField(source="reorder_level")
    dailyUse = serializers.FloatField(source="daily_use")
    highAlert = serializers.BooleanField(source="high_alert")
    batches = BatchSerializer(many=True)

    class Meta:
        model = Medicine
        fields = [
            "id",
            "name",
            "strength",
            "form",
            "category",
            "unit",
            "reorderLevel",
            "dailyUse",
            "location",
            "highAlert",
            "controlled",
            "batches",
        ]
