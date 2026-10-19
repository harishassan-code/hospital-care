from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission

from .models import BloodUnit
from .serializers import BloodUnitCreateSerializer, BloodUnitSerializer
from .services import register_unit


class BloodUnitListView(APIView):
    """GET /api/blood/units/ → the units in the user's hospital (every unit for users without one).
    POST registers a new unit (story #17; blood: edit)."""

    permission_classes = [module_permission("blood")]

    def get(self, request):
        units = BloodUnit.objects.all()
        if request.user.hospital_id:
            units = units.filter(hospital_id=request.user.hospital_id)
        return Response(BloodUnitSerializer(units, many=True, context={"now": timezone.now()}).data)

    def post(self, request):
        serializer = BloodUnitCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = register_unit(serializer, request.user)
        return Response(
            BloodUnitSerializer(unit, context={"now": timezone.now()}).data, status=status.HTTP_201_CREATED
        )
