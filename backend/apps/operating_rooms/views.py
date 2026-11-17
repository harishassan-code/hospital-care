from datetime import date

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.resources.state_machine import TransitionNotAllowed

from . import services
from .models import OperatingRoom, OrCapability, OrStatus
from .serializers import (
    OperatingRoomActionSerializer,
    OperatingRoomSerializer,
    OrBookingCreateSerializer,
    OrBookingSerializer,
)
from .services import apply_operating_room_action, register_operating_room


class OperatingRoomListView(APIView):
    """
    GET /api/operating-rooms/?capability=cardiac&status=available&q=or → rooms in the user's hospital
    (the whole network for users without one). POST registers a room (operatingRooms: edit).
    """

    permission_classes = [module_permission("operatingRooms")]

    def get(self, request):
        rooms = OperatingRoom.objects.select_related("hospital")
        if request.user.hospital_id:
            rooms = rooms.filter(hospital_id=request.user.hospital_id)
        params = request.query_params
        if params.get("capability") in OrCapability.values:
            rooms = rooms.with_capability(params["capability"])
        if params.get("status") in OrStatus.values:
            rooms = rooms.filter(status=params["status"])
        if q := params.get("q", "").strip():
            rooms = rooms.filter(Q(name__icontains=q) | Q(location__icontains=q))
        return Response(OperatingRoomSerializer(rooms, many=True).data)

    def post(self, request):
        serializer = OperatingRoomSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        room = register_operating_room(serializer, request.user)
        return Response(OperatingRoomSerializer(room).data, status=status.HTTP_201_CREATED)


class OperatingRoomActionView(APIView):
    """POST /api/operating-rooms/<id>/actions/ {"action": "startCase", "reason"?} → the room (edit only)."""

    permission_classes = [module_permission("operatingRooms")]

    def post(self, request, pk):
        serializer = OperatingRoomActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            room = apply_operating_room_action(pk, data["action"], actor=request.user, reason=data["reason"])
        except TransitionNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(OperatingRoomSerializer(room).data)


class OperatingRoomScheduleView(APIView):
    """GET /api/operating-rooms/schedule/?date=YYYY-MM-DD (default today, local time) → every room with that
    day's bookings (story #29). Any role that can view operating rooms."""

    permission_classes = [module_permission("operatingRooms")]

    def get(self, request):
        raw = request.query_params.get("date")
        try:
            day = date.fromisoformat(raw) if raw else timezone.localdate()
        except ValueError:
            return Response({"date": ["Use a date like 2026-11-17."]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(services.day_schedule(request.user, day))


class OrBookingListView(APIView):
    """POST /api/operating-rooms/bookings/ {roomId, startsAt, endsAt, procedure, surgeon?, patientInitials?} →
    201 booking (orBookings: edit, so surgeons can book as well as nurses and admins)."""

    permission_classes = [module_permission("orBookings")]

    def post(self, request):
        serializer = OrBookingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        booking = services.book_operating_room(serializer.validated_data, actor=request.user)
        return Response(
            OrBookingSerializer(booking, context={"user": request.user}).data, status=status.HTTP_201_CREATED
        )


class OrBookingCancelView(APIView):
    """POST /api/operating-rooms/bookings/<id>/cancel/ → the booking, now cancelled. 409 if it already is."""

    permission_classes = [module_permission("orBookings")]

    def post(self, request, pk):
        try:
            booking = services.cancel_operating_booking(pk, actor=request.user)
        except TransitionNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(OrBookingSerializer(booking, context={"user": request.user}).data)
