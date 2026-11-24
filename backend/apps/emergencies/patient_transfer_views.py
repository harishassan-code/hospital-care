"""Patient transfers in the API (B17, stories #63 to #65). Every view needs the emergencies module. The rules
are in patient_transfers.py. Shapes are in frontend/src/api/emergencies.ts."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission, own_hospital
from apps.audit.services import record_view
from apps.matching.reservations import release_expired

from .models import EmergencyRequest, PatientTransfer
from .patient_transfers import (
    PatientTransferConflict,
    PatientTransferRefused,
    arrive_patient,
    cancel_patient_transfer,
    in_direction,
    request_patient_transfer,
    visible_to,
)
from .serializers import (
    PatientTransferActionSerializer,
    PatientTransferInputSerializer,
    PatientTransferQuerySerializer,
    PatientTransferSerializer,
)


def refused(exc: PatientTransferRefused) -> Response:
    """A rule the request breaks: 400, under the field it names when there is one."""
    body = {exc.field: [str(exc)]} if exc.field else {"detail": str(exc)}
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def conflict(exc: PatientTransferConflict) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


class CasePatientTransferView(APIView):
    """POST /api/emergencies/<reference>/patient-transfer/ {"destinationId", "note"?} → 201 with the transfer
    (story #64). The case must be visible to the user (404 otherwise), and the user must edit emergencies at
    the case's hospital (admins: any). Refusals are 400 with nothing saved, and a second open transfer is
    409."""

    permission_classes = [module_permission("emergencies")]

    def post(self, request, reference):
        release_expired()  # Story #43: the case's shortfall is worked out after holds that have run out.
        case = get_object_or_404(
            own_hospital(EmergencyRequest.objects.select_related("hospital"), request.user),
            reference=reference,
        )
        serializer = PatientTransferInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            transfer = request_patient_transfer(
                case, destination=data["destinationId"], note=data["note"], actor=request.user
            )
        except PatientTransferRefused as exc:
            return refused(exc)
        except PatientTransferConflict as exc:
            return conflict(exc)
        created = PatientTransfer.objects.with_details().get(pk=transfer.pk)
        return Response(
            PatientTransferSerializer(created, context={"user": request.user}).data,
            status=status.HTTP_201_CREATED,
        )


class PatientTransferListView(APIView):
    """GET /api/patient-transfers/?direction=incoming|outgoing&status= → the patient transfers that involve
    the user's hospital, newest first (every transfer for admins). Incoming is where the user's hospital
    receives the patient, outgoing where it sends one. Without a direction you get both. A bad direction or
    status is 400."""

    permission_classes = [module_permission("emergencies")]

    def get(self, request):
        query = PatientTransferQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        transfers = in_direction(
            visible_to(PatientTransfer.objects.with_details(), request.user),
            request.user,
            data.get("direction"),
        )
        if status_filter := data.get("status"):
            transfers = transfers.filter(status=status_filter)
        data = PatientTransferSerializer(transfers, many=True, context={"user": request.user}).data
        shown = sum(1 for transfer in data if transfer["patientRef"])
        if shown:
            record_view(request.user, "patient-transfers", hospital=request.user.hospital, count=shown)
        return Response(data)


class PatientTransferActionView(APIView):
    """POST /api/patient-transfers/<id>/actions/ {"action": "arrive" | "cancel", "reason"?} → 200 with the
    transfer after the move (story #65). Arrival is the receiving hospital's to confirm. Cancelling is the
    sending hospital's, and needs a reason. A transfer that involves neither of the user's hospitals is 404.
    The sending hospital confirming, or the receiving one cancelling, is 403. A transfer no longer requested,
    or a case whose stock is still on its way, is 409. Nothing changes on any refusal."""

    permission_classes = [module_permission("emergencies")]

    def post(self, request, pk):
        release_expired()  # Story #43: see CasePatientTransferView.
        transfer = get_object_or_404(visible_to(PatientTransfer.objects.all(), request.user), pk=pk)
        serializer = PatientTransferActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            if data["action"] == "arrive":
                arrive_patient(transfer, actor=request.user)
            else:
                cancel_patient_transfer(transfer, actor=request.user, reason=data["reason"])
        except PatientTransferRefused as exc:
            return refused(exc)
        except PatientTransferConflict as exc:
            return conflict(exc)
        moved = PatientTransfer.objects.with_details().get(pk=pk)
        return Response(PatientTransferSerializer(moved, context={"user": request.user}).data)
