"""The simulation's endpoints (B21). The tick is open to every page, signed in or not: it only brings the
city up to its clock, at most once every 15 seconds, and returns nothing private. Everything else is the
CityCare admin's."""

from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsNetworkAdmin
from apps.core import clock

from . import controls, engine


class ControlSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=controls.ACTIONS)
    value = serializers.CharField(required=False, allow_blank=True, default="")


class TickView(APIView):
    """POST /api/simulation/tick/: run the city up to now. Cheap when it is too soon or someone else is."""

    permission_classes = [AllowAny]
    authentication_classes = []  # no session, so no CSRF check: the request carries nothing but "now"

    def post(self, request):
        result = engine.run()
        return Response(
            {
                "ran": result["ran"],
                "behind": result.get("behind", False),
                "mode": clock.reading().mode,
                "cityTime": clock.now(),
            }
        )


class SimulationView(APIView):
    """GET /api/simulation/: the panel's state and the latest 50 events."""

    permission_classes = [IsNetworkAdmin]

    def get(self, request):
        return Response(controls.status())


class ControlView(APIView):
    """POST /api/simulation/control/ {action, value}: pause, resume, speed, fastForward, catchUp, scenario,
    massCasualty or endIncident."""

    permission_classes = [IsNetworkAdmin]

    def post(self, request):
        data = ControlSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        controls.apply(data.validated_data["action"], data.validated_data["value"], actor=request.user)
        return Response(controls.status(), status=status.HTTP_200_OK)


class AdvanceView(APIView):
    """POST /api/simulation/advance/: run the next stretch now (the panel calls it while fast-forwarding)."""

    permission_classes = [IsNetworkAdmin]

    def post(self, request):
        result = engine.run(force=True)
        body = controls.status()
        body["ran"], body["behind"] = result["ran"], result.get("behind", False)
        return Response(body)
