"""Reservations and allocations in the API (stories #45, #46). Shapes: frontend/src/api/emergencies.ts."""

from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import can_see, own_hospital
from apps.emergencies.models import ResourceType, severity_rank
from apps.emergencies.serializers import (
    AllocateManySerializer,
    AllocationInputSerializer,
    AllocationSerializer,
    HeldQuerySerializer,
    HeldReservationSerializer,
)
from apps.resources.state_machine import TransitionNotAllowed

from .allocations import ALLOCATION_MODULE, AllocationRefused, allocate, allocate_many
from .models import Reservation, ReservationStatus
from .reservations import ReservationNotHeld, release_expired


def visible_types(user) -> list[str]:
    """The resource types the user's role can see (the module view for each type)."""
    return [kind for kind in ResourceType.values if can_see(user.effective_role, ALLOCATION_MODULE[kind])]


class HeldReservationListView(APIView):
    """GET /api/reservations/?status=held&type=blood → the held reservations at the user's hospital (every
    hospital for admins). Most urgent first: severity, then the case waiting longest, then the hold expiring
    first. Only the types the user's role can see. `canAllocate` says whether the user may allocate each one.
    A `type` the role can't see, or a role that sees no type, is 403."""

    # Signed in only here: which resource types a role may see or allocate is checked per hold, below.
    permission_classes = [IsAuthenticated]

    def get(self, request):
        release_expired()  # Story #43: a hold that has run out goes back to stock before it is listed.
        query = HeldQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        visible = visible_types(request.user)
        kind = query.validated_data.get("type")
        if not visible or (kind and kind not in visible):
            raise PermissionDenied("Your role can't see this.")
        held = Reservation.objects.filter(
            status=ReservationStatus.HELD, request_item__resource_type__in=visible
        )
        holds = (
            own_hospital(held, request.user)
            .select_related("request_item__request", "reserved_by")
            .prefetch_related("resource")
            .annotate(priority=severity_rank("request_item__request__severity"))
            .order_by("priority", "request_item__request__created_at", "expires_at", "id")
        )
        if kind:
            holds = holds.filter(request_item__resource_type=kind)
        return Response(HeldReservationSerializer(holds, many=True, context={"user": request.user}).data)


class ReservationAllocateView(APIView):
    """POST /api/reservations/<id>/allocate/ {"note"?} → 201 with the allocation (story #45).

    Another hospital's hold is 404, unless the user is an admin. A role that can't allocate the type, or a
    resource at another hospital, is 403. A hold that is no longer held (allocated, released, or past its
    expiry), or a case that is closed, cancelled or fulfilled, is 409, and nothing changes."""

    # Signed in only here: which resource types a role may see or allocate is checked per hold, below.
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        release_expired()  # Story #43: a hold that has just run out is expired, so it answers 409.
        if not own_hospital(Reservation.objects.all(), request.user).filter(pk=pk).exists():
            raise Http404("No reservation with that id.")
        serializer = AllocationInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            allocation = allocate(pk, actor=request.user, note=serializer.validated_data["note"])
        except (ReservationNotHeld, AllocationRefused, TransitionNotAllowed) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AllocationSerializer(allocation).data, status=status.HTTP_201_CREATED)


class ReservationAllocateManyView(APIView):
    """POST /api/reservations/allocate/ {"ids": [...]} → 201 with the allocations, in the order asked (#46).

    All or none: if one hold can't be allocated, nothing changes, and the answer is 409 (403 for a hold the
    user can't allocate). A hold the user can't see is 404."""

    # Signed in only here: which resource types a role may see or allocate is checked per hold, below.
    permission_classes = [IsAuthenticated]

    def post(self, request):
        release_expired()  # Story #43: see ReservationAllocateView.
        serializer = AllocateManySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        if own_hospital(Reservation.objects.filter(pk__in=ids), request.user).count() != len(ids):
            raise Http404("No reservation with one of those ids.")
        try:
            allocations = allocate_many(ids, actor=request.user)
        except (ReservationNotHeld, AllocationRefused, TransitionNotAllowed) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AllocationSerializer(allocations, many=True).data, status=status.HTTP_201_CREATED)
