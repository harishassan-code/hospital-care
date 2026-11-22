"""Transfers in the API (stories #47, #48, #49). Every view needs the transfers module; the rules are in
services.py."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission, own_hospital
from apps.ambulances.serializers import TripDispatchSerializer, TripSerializer
from apps.ambulances.services import dispatch_trip, trips_with_details
from apps.emergencies.models import EmergencyRequest, RequestItem
from apps.matching.reservations import release_expired
from apps.resources.state_machine import TransitionNotAllowed

from .models import Transfer
from .serializers import (
    TransferActionSerializer,
    TransferInputSerializer,
    TransferQuerySerializer,
    TransferSerializer,
)
from .services import (
    TransferConflict,
    TransferRefused,
    approve,
    cancel,
    dispatch,
    in_direction,
    receive,
    reject,
    request_transfer,
    start_transit,
    visible_to,
)


def refused(exc: TransferRefused) -> Response:
    """A rule the request breaks: 400, under the field it names when there is one."""
    body = {exc.field: [str(exc)]} if exc.field else {"detail": str(exc)}
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


def conflict(exc: TransferConflict) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)


def run_move(action: str, transfer: Transfer, *, actor, reason: str, note: str) -> Transfer:
    """Make the move the action names. The services check who may make it and what the lifecycle allows."""
    if action == "approve":
        return approve(transfer, actor=actor, note=note)
    if action == "reject":
        return reject(transfer, actor=actor, reason=reason, note=note)
    if action == "dispatch":
        return dispatch(transfer, actor=actor, note=note)
    if action == "startTransit":
        return start_transit(transfer, actor=actor, note=note)
    if action == "deliver":
        return receive(transfer, actor=actor, note=note)
    return cancel(transfer, actor=actor, reason=reason, note=note)


class TransferListView(APIView):
    """GET /api/transfers/?direction=incoming|outgoing&status= → the transfers that involve the user's
    hospital, newest first (every transfer for admins). POST asks another hospital for stock of one of a
    case's needs (story #47) → 201 with the transfer. The case must be visible to the user (404 otherwise).
    Transfers: edit."""

    permission_classes = [module_permission("transfers")]

    def get(self, request):
        release_expired()  # Story #43: holds that have run out are stock again before the list is read.
        query = TransferQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        transfers = in_direction(
            visible_to(Transfer.objects.with_details(), request.user), request.user, data.get("direction")
        )
        if status_filter := data.get("status"):
            transfers = transfers.filter(status=status_filter)
        return Response(TransferSerializer(transfers, many=True, context={"user": request.user}).data)

    def post(self, request):
        release_expired()  # Story #43: see get.
        serializer = TransferInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        cases = own_hospital(EmergencyRequest.objects.all(), request.user)
        item = get_object_or_404(RequestItem.objects.filter(request__in=cases), pk=data["itemId"])
        try:
            transfer = request_transfer(
                item,
                supplier=data["supplierId"],
                quantity=data["quantity"],
                actor=request.user,
                note=data["note"],
            )
        except TransferRefused as exc:
            return refused(exc)
        created = Transfer.objects.with_details().get(pk=transfer.pk)
        return Response(
            TransferSerializer(created, context={"user": request.user}).data, status=status.HTTP_201_CREATED
        )


class TransferDetailView(APIView):
    """GET /api/transfers/<id>/ → the transfer with its history and the moves the user may make now. A
    transfer that involves neither of the user's hospitals is 404 (admins see all)."""

    permission_classes = [module_permission("transfers")]

    def get(self, request, pk):
        release_expired()  # Story #43: see TransferListView.
        transfer = get_object_or_404(visible_to(Transfer.objects.with_details(), request.user), pk=pk)
        return Response(TransferSerializer(transfer, context={"user": request.user}).data)


class TransferActionView(APIView):
    """POST /api/transfers/<id>/actions/ {"action", "reason"?, "note"?} → 200 with the transfer after the
    move. Actions: approve, reject (reason required), dispatch, startTransit, deliver (confirm receipt) and
    cancel. 403 when the user may not make the move, 409 when the lifecycle or the stock doesn't allow it,
    404 for a transfer that involves neither of the user's hospitals. Nothing changes on any refusal."""

    permission_classes = [module_permission("transfers")]

    def post(self, request, pk):
        release_expired()  # Story #43: see TransferListView.
        transfer = get_object_or_404(visible_to(Transfer.objects.all(), request.user), pk=pk)
        serializer = TransferActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            run_move(data["action"], transfer, actor=request.user, reason=data["reason"], note=data["note"])
        except TransferRefused as exc:
            return refused(exc)
        except TransferConflict as exc:
            return conflict(exc)
        moved = Transfer.objects.with_details().get(pk=pk)
        return Response(TransferSerializer(moved, context={"user": request.user}).data)


class TransferTripView(APIView):
    """POST /api/transfers/<id>/trips/ {"ambulance": <id>} → 201 with the trip (story #51). Sends an
    available ambulance from the supplying hospital to carry an approved transfer. Needs edit on
    ambulances at the supplier (403 otherwise, the receiving hospital included). 404 for a transfer or an
    ambulance the user can't see. 409 when the transfer isn't approved, the ambulance isn't available, or
    a trip is already on the road. 400 when the ambulance isn't based at the supplier. Nothing changes on
    any refusal."""

    permission_classes = [module_permission("ambulances")]

    def post(self, request, pk):
        transfer = get_object_or_404(visible_to(Transfer.objects.all(), request.user), pk=pk)
        serializer = TripDispatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            trip = dispatch_trip(
                transfer, ambulance_id=serializer.validated_data["ambulance"], actor=request.user
            )
        except (TransferConflict, TransitionNotAllowed) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        created = trips_with_details().get(pk=trip.pk)
        return Response(
            TripSerializer(created, context={"user": request.user}).data, status=status.HTTP_201_CREATED
        )
