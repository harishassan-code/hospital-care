from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.resources.state_machine import TransitionNotAllowed
from apps.transfers.models import Transfer
from apps.transfers.serializers import TransferSerializer
from apps.transfers.services import visible_to
from .models import Ambulance, AmbulanceStatus, AmbulanceType, Trip
from .serializers import (
    AmbulanceActionSerializer,
    AmbulanceSerializer,
    DispatchTripSerializer,
    TripActionSerializer,
)
from .services import TripConflict, TripRefused, advance_trip, dispatch_for_transfer, register_ambulance
from .services import apply_ambulance_action


class AmbulanceListView(APIView):
    """GET /api/ambulances/?type=&status=&q= → ambulances in the user's hospital (network for admins).
    POST registers an ambulance at the actor's hospital (ambulances: edit)."""

    permission_classes = [module_permission("ambulances")]

    def get(self, request):
        items = Ambulance.objects.select_related("hospital")
        if request.user.hospital_id:
            items = items.filter(hospital_id=request.user.hospital_id)
        params = request.query_params
        if params.get("type") in AmbulanceType.values:
            items = items.filter(ambulance_type=params["type"])
        if params.get("status") in AmbulanceStatus.values:
            items = items.filter(status=params["status"])
        if q := params.get("q", "").strip():
            items = items.filter(Q(identifier__icontains=q))
        return Response(AmbulanceSerializer(items, many=True).data)

    def post(self, request):
        serializer = AmbulanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ambulance = register_ambulance(serializer, request.user)
        return Response(AmbulanceSerializer(ambulance).data, status=status.HTTP_201_CREATED)


class AmbulanceActionView(APIView):
    permission_classes = [module_permission("ambulances")]

    def post(self, request, pk):
        serializer = AmbulanceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            ambulance = apply_ambulance_action(pk, data["action"], actor=request.user, reason=data["reason"])
        except TransitionNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AmbulanceSerializer(ambulance).data)


def trip_refused(exc: TripRefused) -> Response:
    body = {exc.field: [str(exc)]} if exc.field else {"detail": str(exc)}
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def trip_conflict(exc: TripConflict) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class TransferTripView(APIView):
    """POST /api/transfers/<id>/trip/ {"ambulanceId"} → dispatch an available ambulance (transfers: edit)."""

    permission_classes = [module_permission("transfers")]

    def post(self, request, pk):
        transfer = get_object_or_404(visible_to(Transfer.objects.all(), request.user), pk=pk)
        serializer = DispatchTripSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            dispatch_for_transfer(transfer, ambulance_id=serializer.validated_data["ambulanceId"], actor=request.user)
        except TripRefused as exc:
            return trip_refused(exc)
        except TripConflict as exc:
            return trip_conflict(exc)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        moved = Transfer.objects.with_details().get(pk=pk)
        return Response(TransferSerializer(moved, context={"user": request.user}).data)


class TripActionView(APIView):
    """POST /api/trips/<id>/actions/ → advance a simulated trip (transfers: edit)."""

    permission_classes = [module_permission("transfers")]

    def post(self, request, pk):
        trip = get_object_or_404(Trip.objects.select_related("transfer"), pk=pk)
        get_object_or_404(visible_to(Transfer.objects.all(), request.user), pk=trip.transfer_id)
        serializer = TripActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            advance_trip(pk, serializer.validated_data["action"], actor=request.user)
        except TripConflict as exc:
            return trip_conflict(exc)
        except PermissionDenied as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        moved = Transfer.objects.with_details().get(pk=trip.transfer_id)
        return Response(TransferSerializer(moved, context={"user": request.user}).data)