"""Specialists in the API (B16, stories #61 and #62). Every view needs the specialists module: everyone on
staff reads the whole network, and only admins and nurses write (nurses at their own hospital). The rules
are in services.py."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.core import clock

from .models import Specialist
from .serializers import (
    OnCallWindowInputSerializer,
    OnCallWindowSerializer,
    SpecialistDetailSerializer,
    SpecialistInputSerializer,
    SpecialistQuerySerializer,
    SpecialistSerializer,
    SpecialistUpdateSerializer,
)
from .services import (
    SpecialistConflict,
    add_on_call_window,
    create_specialist,
    remove_on_call_window,
    update_specialist,
)


def _detail(pk: int, now) -> dict:
    """The specialist as the detail page shows it, reloaded so the response matches a GET."""
    specialist = get_object_or_404(Specialist.objects.with_schedule(now), pk=pk)
    return SpecialistDetailSerializer(specialist, context={"now": now}).data


class SpecialistListView(APIView):
    """GET /api/specialists/?hospital=&specialty=&availableNow=true → every specialist in the network, active
    and deactivated, by hospital, then specialty, then name. `availableNow=true` keeps only those on call at
    the server's clock. POST lists a new specialist (specialists: edit, own hospital unless admin) → 201."""

    permission_classes = [module_permission("specialists")]

    def get(self, request):
        query = SpecialistQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        data = query.validated_data
        now = clock.now()  # read once, so one response never mixes two moments
        specialists = Specialist.objects.with_schedule(now)
        if data.get("hospital") is not None:
            specialists = specialists.filter(hospital_id=data["hospital"])
        if data.get("specialty"):
            specialists = specialists.filter(specialty__iexact=data["specialty"])
        if data["availableNow"]:
            specialists = specialists.available_at(now)
        specialists = specialists.order_by("hospital__name", "specialty", "name", "id")
        return Response(SpecialistSerializer(specialists, many=True, context={"now": now}).data)

    def post(self, request):
        serializer = SpecialistInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        specialist = create_specialist(
            data["hospitalId"], name=data["name"], specialty=data["specialty"], actor=request.user
        )
        return Response(_detail(specialist.pk, clock.now()), status=status.HTTP_201_CREATED)


class SpecialistDetailView(APIView):
    """GET /api/specialists/<id>/ → one specialist with its windows that haven't ended. PATCH changes its
    name, specialty or whether it is active (own hospital unless admin). A deactivated specialist stays,
    marked."""

    permission_classes = [module_permission("specialists")]

    def get(self, request, pk):
        return Response(_detail(pk, clock.now()))

    def patch(self, request, pk):
        serializer = SpecialistUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        update_specialist(pk, serializer.validated_data, actor=request.user)
        return Response(_detail(pk, clock.now()))


class OnCallWindowListView(APIView):
    """POST /api/specialists/<id>/on-call/ {startsAt, endsAt} → 201 the window (specialists: edit, own
    hospital unless admin). 400 when it doesn't end after it starts, has already ended, or overlaps another
    window."""

    permission_classes = [module_permission("specialists")]

    def post(self, request, pk):
        serializer = OnCallWindowInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        window = add_on_call_window(
            pk,
            starts_at=data["startsAt"],
            ends_at=data["endsAt"],
            actor=request.user,
            now=clock.now(),
        )
        return Response(OnCallWindowSerializer(window).data, status=status.HTTP_201_CREATED)


class OnCallWindowDetailView(APIView):
    """DELETE /api/specialists/<id>/on-call/<window>/ → 204 (specialists: edit, own hospital unless admin).
    409 once the window has started: it stays as history. 404 when the window isn't this specialist's."""

    permission_classes = [module_permission("specialists")]

    def delete(self, request, pk, window):
        try:
            remove_on_call_window(pk, window, actor=request.user, now=clock.now())
        except SpecialistConflict as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
