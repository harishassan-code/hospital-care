import datetime as dt

from rest_framework import serializers

from .models import AuditLog


class AuditEntrySerializer(serializers.ModelSerializer):
    """Shape of an audit entry in frontend/src/api/audit.ts. Times are ISO 8601 in UTC."""

    at = serializers.DateTimeField(read_only=True, default_timezone=dt.timezone.utc)
    actorEmail = serializers.CharField(source="actor_email", read_only=True)
    targetType = serializers.CharField(source="target_type", read_only=True)
    targetId = serializers.CharField(source="target_id", read_only=True)
    targetRepr = serializers.CharField(source="target_repr", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "at",
            "actorEmail",
            "action",
            "targetType",
            "targetId",
            "targetRepr",
            "reason",
            "before",
            "after",
        ]
        read_only_fields = fields
