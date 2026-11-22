"""Notifications in the API (story #52; bolt B06). Each signed-in staff member sees only their own rows. The
rules are in services.py."""

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStaff

from .serializers import NotificationQuerySerializer, NotificationSerializer
from .services import inbox, mark_read, unread_count


class NotificationListView(APIView):
    """GET /api/notifications/ → the user's 50 newest notifications, newest first; `?unread=true` keeps only
    the unread ones. Staff only (403 for patients and signed-out users). Without a hospital, the list is
    their own rows only, which is empty for an admin who has none."""

    permission_classes = [IsStaff]

    def get(self, request):
        query = NotificationQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        rows = inbox(request.user, unread_only=query.validated_data["unread"])
        return Response(NotificationSerializer(rows, many=True).data)


class NotificationUnreadCountView(APIView):
    """GET /api/notifications/unread-count/ → {"count": n}, the user's unread notifications."""

    permission_classes = [IsStaff]

    def get(self, request):
        return Response({"count": unread_count(request.user)})


class NotificationReadView(APIView):
    """POST /api/notifications/<id>/read/ → the notification with `readAt` set. Setting it again keeps the
    first time. Another user's notification is 404, as if it didn't exist. Writes `notification.read` on
    the first call."""

    permission_classes = [IsStaff]

    def post(self, request, pk):
        row = mark_read(pk, user=request.user)
        return Response(NotificationSerializer(row).data)
