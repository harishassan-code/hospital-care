from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.emergencies.services import escalate_overdue
from apps.matching.reservations import release_expired

from .services import network_figures


class CommandCentreView(APIView):
    """GET /api/command-centre/ → the whole network's figures in one read (story #55). Admins only.

    The request-time sweeps run first, as the feed and the case pages do, so held stock and escalated cases
    agree with the case pages."""

    permission_classes = [module_permission("commandCentre")]

    def get(self, request):
        escalate_overdue()  # Story #35
        release_expired()  # Story #43
        return Response(network_figures())
