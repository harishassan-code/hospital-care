from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Role
from apps.accounts.permissions import module_permission
from apps.resources.state_machine import TransitionNotAllowed
from apps.transfers.services import TransferConflict

from . import services
from .models import MANUAL_ACTIONS, Ambulance, AmbulanceStatus, AmbulanceType, Trip


class AmbulanceSerializer(serializers.ModelSerializer):
    """Shape of `Ambulance` in frontend/src/api/ambulances.ts. POST uses the same fields."""

    type = serializers.ChoiceField(source="ambulance_type", choices=AmbulanceType.choices)
    status = serializers.CharField(read_only=True)
    statusSince = serializers.DateTimeField(source="status_since", read_only=True)
    hospital = serializers.CharField(source="hospital.name", read_only=True)
    hospitalId = serializers.IntegerField(source="hospital_id", required=False, allow_null=True)

    class Meta:
        model = Ambulance
        fields = [
            "id",
            "identifier",
            "type",
            "plate",
            "note",
            "status",
            "statusSince",
            "hospital",
            "hospitalId",
        ]

    def validate_identifier(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Enter the fleet number.")
        if Ambulance.objects.filter(identifier__iexact=value).exists():
            raise serializers.ValidationError("This fleet number is already registered.")
        return value


def trip_data(trip: Trip) -> dict:
    """A trip as the Transfers page shows it. Also used inside the transfer serializer."""
    stamp = serializers.DateTimeField().to_representation
    return {
        "id": trip.pk,
        "ambulance": {"id": trip.ambulance_id, "identifier": trip.ambulance.identifier},
        "status": trip.status,
        "etaMinutes": trip.eta_minutes,
        "dispatchedAt": stamp(trip.dispatched_at),
        "arrivedAt": stamp(trip.arrived_at) if trip.arrived_at else None,
    }


class AmbulanceListView(APIView):
    """GET /api/ambulances/?type=als&status=available&hospital=3 → the fleet (own hospital; admins all).
    POST registers one (ambulances: edit)."""

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
        if params.get("hospital", "").isdigit():
            items = items.filter(hospital_id=int(params["hospital"]))
        return Response(AmbulanceSerializer(items, many=True).data)

    def post(self, request):
        serializer = AmbulanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ambulance = services.register_ambulance(serializer, request.user)
        return Response(AmbulanceSerializer(ambulance).data, status=status.HTTP_201_CREATED)


class ActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=MANUAL_ACTIONS)
    reason = serializers.CharField(max_length=300, required=False, allow_blank=True, default="")


class AmbulanceActionView(APIView):
    """POST /api/ambulances/<id>/actions/ {"action": "startMaintenance"} → the updated ambulance."""

    permission_classes = [module_permission("ambulances")]

    def post(self, request, pk):
        data = ActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            ambulance = services.apply_ambulance_action(
                pk, data.validated_data["action"], actor=request.user, reason=data.validated_data["reason"]
            )
        except TransitionNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AmbulanceSerializer(ambulance).data)


class AvailableForDispatchView(APIView):
    """GET /api/ambulances/available/?hospital=<id> → the available ambulances at that hospital, for the
    dispatch picker on a transfer. Under the transfers module, so the supplier's blood bank can dispatch
    without seeing the fleet registry; non-admins only get their own hospital's."""

    permission_classes = [module_permission("transfers")]

    def get(self, request):
        hospital = request.query_params.get("hospital", "")
        if request.user.effective_role != Role.ADMIN:
            hospital = str(request.user.hospital_id or "")
        if not hospital.isdigit():
            return Response([])
        items = Ambulance.objects.select_related("hospital").filter(
            hospital_id=int(hospital), status=AmbulanceStatus.AVAILABLE
        )
        return Response(AmbulanceSerializer(items, many=True).data)


class DispatchSerializer(serializers.Serializer):
    transferId = serializers.IntegerField()
    ambulanceId = serializers.IntegerField()


class TripListView(APIView):
    """POST /api/ambulances/trips/ {"transferId", "ambulanceId"} → the new trip (story #51). Who may dispatch
    is the transfer's rule (supplier staff with edit on the resource's module)."""

    permission_classes = [module_permission("transfers")]

    def post(self, request):
        data = DispatchSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            trip = services.dispatch_trip(
                data.validated_data["transferId"], data.validated_data["ambulanceId"], actor=request.user
            )
        except (TransitionNotAllowed, TransferConflict) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(trip_data(trip), status=status.HTTP_201_CREATED)


class TripActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["enRoute", "arrive"])


class TripActionView(APIView):
    """POST /api/ambulances/trips/<id>/actions/ {"action": "enRoute" | "arrive"} → the trip."""

    permission_classes = [module_permission("transfers")]

    def post(self, request, pk):
        data = TripActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            trip = services.advance_trip(pk, data.validated_data["action"], actor=request.user)
        except (TransitionNotAllowed, TransferConflict) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(trip_data(trip))
