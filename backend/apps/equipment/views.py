from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission

from .models import Equipment, EquipmentStatus, EquipmentType
from .serializers import EquipmentSerializer
from .services import register_equipment


class EquipmentListView(APIView):
    """
    GET /api/equipment/?type=ventilator&status=available&q=icu → equipment in the user's hospital
    (the whole network for users without one). POST registers new equipment (equipment: edit).
    """

    permission_classes = [module_permission("equipment")]

    def get(self, request):
        items = Equipment.objects.select_related("hospital")
        if request.user.hospital_id:
            items = items.filter(hospital_id=request.user.hospital_id)
        params = request.query_params
        if params.get("type") in EquipmentType.values:
            items = items.filter(equipment_type=params["type"])
        if params.get("status") in EquipmentStatus.values:
            items = items.filter(status=params["status"])
        if q := params.get("q", "").strip():
            items = items.filter(Q(identifier__icontains=q) | Q(name__icontains=q) | Q(location__icontains=q))
        return Response(EquipmentSerializer(items, many=True).data)

    def post(self, request):
        serializer = EquipmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        equipment = register_equipment(serializer, request.user)
        return Response(EquipmentSerializer(equipment).data, status=status.HTTP_201_CREATED)
