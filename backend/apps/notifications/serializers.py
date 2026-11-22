"""Shape of `Notification` in the frontend's api/notifications.ts (camelCase, like the other modules)."""

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    createdAt = serializers.DateTimeField(source="created_at", read_only=True)
    readAt = serializers.DateTimeField(source="read_at", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "kind", "severity", "message", "link", "createdAt", "readAt"]


class NotificationQuerySerializer(serializers.Serializer):
    """GET /api/notifications/?unread=true. `1` is accepted too; anything else that isn't a boolean is 400."""

    unread = serializers.BooleanField(required=False, default=False)
