"""The public network pages' data (B19): no sign-in needed, nothing that identifies a patient. The session is
read
(never required) so that signed-in hospital staff see doctors' names; a GET needs no CSRF token."""

from django.http import Http404
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .network import hospital_profile, network_snapshot, public_hospital, public_hospitals


class PublicNetworkView(APIView):
    """GET /api/public/network/: the city at a glance."""

    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]

    def get(self, request):
        return Response(network_snapshot())


class PublicHospitalListView(APIView):
    """GET /api/public/hospitals/: the member hospitals with their emergency status."""

    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]

    def get(self, request):
        return Response(public_hospitals())


class PublicHospitalDetailView(APIView):
    """GET /api/public/hospitals/<id>/: one hospital's public page. Unknown or inactive: 404."""

    permission_classes = [AllowAny]
    authentication_classes = [SessionAuthentication]

    def get(self, request, pk: int):
        hospital = public_hospital(pk)
        if hospital is None:
            raise Http404
        staff = request.user.is_authenticated and request.user.is_hospital_staff
        return Response(hospital_profile(hospital, show_names=staff))
