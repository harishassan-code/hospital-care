from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role

from . import services

PAGE_SIZE = 50


class StaffOnly(BasePermission):
    """Any signed-in staff role. Which notifications they see is narrowed in services.for_user."""

    message = "Only staff receive notifications."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.effective_role != Role.PATIENT)


class NotificationSerializer(serializers.Serializer):
    """Shape of `Notification` in frontend/src/api/notifications.ts."""

    id = serializers.IntegerField()
    kind = serializers.CharField()
    severity = serializers.CharField()
    title = serializers.CharField()
    body = serializers.CharField()
    link = serializers.CharField()
    createdAt = serializers.DateTimeField(source="created_at")
    read = serializers.BooleanField(source="is_read")
    acknowledged = serializers.BooleanField(source="is_acknowledged")


class NotificationListView(APIView):
    """GET /api/notifications/?unread=1&critical=1 → my latest notifications, newest first (story #52)."""

    permission_classes = [StaffOnly]

    def get(self, request):
        items = services.for_user(request.user)
        if request.query_params.get("unread") == "1":
            items = items.filter(is_read=False)
        if request.query_params.get("critical") == "1":
            items = items.filter(severity="critical", is_acknowledged=False)
        return Response(NotificationSerializer(items[:PAGE_SIZE], many=True).data)


class UnreadCountView(APIView):
    """GET /api/notifications/unread-count/ → {"unread": n, "critical": n unacknowledged critical}."""

    permission_classes = [StaffOnly]

    def get(self, request):
        items = services.for_user(request.user)
        return Response(
            {
                "unread": items.filter(is_read=False).count(),
                "critical": items.filter(severity="critical", is_acknowledged=False).count(),
            }
        )


class ReadView(APIView):
    """POST /api/notifications/<id>/read/ → 204."""

    permission_classes = [StaffOnly]

    def post(self, request, pk):
        services.mark_read(get_object_or_404(services.for_user(request.user), pk=pk), request.user)
        return Response(status=204)


class ReadAllView(APIView):
    """POST /api/notifications/read-all/ → {"marked": n}."""

    permission_classes = [StaffOnly]

    def post(self, request):
        return Response({"marked": services.mark_all_read(request.user)})


class AcknowledgeView(APIView):
    """POST /api/notifications/<id>/acknowledge/ → 204. Clears a critical banner for this user."""

    permission_classes = [StaffOnly]

    def post(self, request, pk):
        services.acknowledge(get_object_or_404(services.for_user(request.user), pk=pk), request.user)
        return Response(status=204)
