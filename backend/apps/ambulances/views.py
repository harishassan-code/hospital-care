from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.resources.state_machine import TransitionNotAllowed
from apps.transfers.models import Transfer
from apps.transfers.services import TransferConflict, visible_to

from .models import TRIP_ACTIVE, AmbulanceStatus, AmbulanceType, Trip
from .serializers import (
    AmbulanceActionSerializer,
    AmbulanceSerializer,
    TripActionSerializer,
    TripSerializer,
)
from .services import (
    apply_ambulance_action,
    register_ambulance,
    step_trip,
    trips_with_details,
    visible_ambulances,
)


class AmbulanceListView(APIView):
    """GET /api/ambulances/?type=basic&status=available&q=amb-0&hospital=3 → the user's hospital's ambulances
    (admins: all). `hospital` is a hospital id. POST registers an ambulance (ambulances: edit)."""

    permission_classes = [module_permission("ambulances")]

    def get(self, request):
        active = Prefetch(
            "trips", queryset=Trip.objects.filter(status__in=TRIP_ACTIVE), to_attr="active_trips"
        )
        items = visible_ambulances(request.user).select_related("hospital").prefetch_related(active)
        params = request.query_params
        if params.get("type") in AmbulanceType.values:
            items = items.filter(type=params["type"])
        if params.get("status") in AmbulanceStatus.values:
            items = items.filter(status=params["status"])
        if params.get("hospital", "").isdigit():
            items = items.filter(hospital_id=int(params["hospital"]))
        if q := params.get("q", "").strip():
            items = items.filter(Q(identifier__icontains=q))
        return Response(AmbulanceSerializer(items, many=True).data)

    def post(self, request):
        serializer = AmbulanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ambulance = register_ambulance(serializer, request.user)
        return Response(AmbulanceSerializer(ambulance).data, status=status.HTTP_201_CREATED)


class AmbulanceActionView(APIView):
    """POST /api/ambulances/<id>/actions/ {"action": "outOfService", "reason"?} → the ambulance (edit). The
    trip's moves (dispatch, release) are 409: a trip makes them."""

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


class TripActionView(APIView):
    """POST /api/trips/<id>/actions/ {"action": "depart" | "arrive" | "complete", "note"?} → 200 with the
    trip after the step. Any other step is 409 and changes nothing. 403 for a user who may not step the
    trip (the receiving hospital, or no edit on ambulances at the supplier). 404 for a trip whose transfer
    the user can't see. The transfer follows: departing puts it in transit, completing leaves it for the
    receiver to confirm."""

    permission_classes = [module_permission("ambulances")]

    def post(self, request, pk):
        trip = get_object_or_404(
            trips_with_details().filter(transfer__in=visible_to(Transfer.objects.all(), request.user)), pk=pk
        )
        serializer = TripActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            step_trip(trip, data["action"], actor=request.user, note=data["note"])
        except (TransitionNotAllowed, TransferConflict) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(TripSerializer(trips_with_details().get(pk=pk), context={"user": request.user}).data)
