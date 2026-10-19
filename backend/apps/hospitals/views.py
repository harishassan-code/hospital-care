from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.resources.state_machine import TransitionNotAllowed

from .models import Bed, Capability, Department, Hospital, StorageLocation, Ward
from .serializers import (
    BedActionSerializer,
    BedSerializer,
    CapabilitySerializer,
    DepartmentSerializer,
    HospitalDetailSerializer,
    HospitalSerializer,
    LocationSerializer,
    WardItemSerializer,
    WardSerializer,
)
from .services import add_structure_item, apply_bed_action, remove_structure_item, save_hospital


class BedBoardView(APIView):
    """
    GET /api/beds/ → {wards, beds}, the shape of `BedBoard` in frontend/src/api/beds.ts.
    Limited to the user's hospital when they have one.
    """

    permission_classes = [module_permission("beds")]

    def get(self, request):
        wards = Ward.objects.all()
        beds = Bed.objects.select_related("ward")
        if request.user.hospital_id:
            wards = wards.filter(hospital_id=request.user.hospital_id)
            beds = beds.filter(ward__hospital_id=request.user.hospital_id)
        return Response(
            {"wards": WardSerializer(wards, many=True).data, "beds": BedSerializer(beds, many=True).data}
        )


class BedActionView(APIView):
    """POST /api/beds/<label>/actions/ {"action": "discharge"} → the updated bed."""

    permission_classes = [module_permission("beds")]

    def post(self, request, label):
        serializer = BedActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not Bed.objects.filter(label=label).exists():
            return Response({"detail": "No bed with that id."}, status=status.HTTP_404_NOT_FOUND)
        try:
            bed = apply_bed_action(label, serializer.validated_data["action"], actor=request.user)
        except TransitionNotAllowed as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(BedSerializer(bed).data)


class HospitalListView(APIView):
    """GET /api/hospitals/ every hospital (active or not); POST registers one (admins)."""

    permission_classes = [module_permission("hospitals")]

    def get(self, request):
        hospitals = Hospital.objects.prefetch_related("capabilities")
        return Response(HospitalSerializer(hospitals, many=True).data)

    def post(self, request):
        serializer = HospitalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hospital = save_hospital(serializer, request.user)
        return Response(HospitalSerializer(hospital).data, status=status.HTTP_201_CREATED)


class HospitalDetailView(APIView):
    """GET /api/hospitals/<id>/ with its structure. PATCH changes fields, e.g. {"isActive": false}."""

    permission_classes = [module_permission("hospitals")]

    def get(self, request, pk):
        hospital = get_object_or_404(Hospital.objects.prefetch_related("capabilities"), pk=pk)
        return Response(HospitalDetailSerializer(hospital).data)

    def patch(self, request, pk):
        hospital = get_object_or_404(Hospital, pk=pk)
        serializer = HospitalSerializer(hospital, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(HospitalSerializer(save_hospital(serializer, request.user)).data)


class CapabilityListView(APIView):
    """GET /api/hospitals/capabilities/: the managed list a hospital's capabilities come from."""

    permission_classes = [module_permission("hospitals")]

    def get(self, request):
        return Response(CapabilitySerializer(Capability.objects.all(), many=True).data)


STRUCTURE = {
    "departments": (Department, DepartmentSerializer),
    "wards": (Ward, WardItemSerializer),
    "locations": (StorageLocation, LocationSerializer),
}

IN_USE = {
    "departments": "This department is still in use.",
    "wards": "This ward still has beds. Move or remove them first.",
    "locations": "Resources are still stored here. Move them first.",
}


class StructureListView(APIView):
    """POST /api/hospitals/<id>/<departments|wards|locations>/ adds one (admins)."""

    permission_classes = [module_permission("hospitals")]

    def post(self, request, pk, kind):
        hospital = get_object_or_404(Hospital, pk=pk)
        _, serializer_class = STRUCTURE[kind]
        serializer = serializer_class(data=request.data, context={"hospital": hospital})
        serializer.is_valid(raise_exception=True)
        add_structure_item(serializer, hospital, request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StructureItemView(APIView):
    """DELETE /api/hospitals/<id>/<kind>/<item id>/ (admins). 409 while something still uses it."""

    permission_classes = [module_permission("hospitals")]

    def delete(self, request, pk, kind, item):
        model, _ = STRUCTURE[kind]
        obj = get_object_or_404(model, pk=item, hospital_id=pk)
        try:
            remove_structure_item(obj, request.user)
        except ProtectedError:
            return Response({"detail": IN_USE[kind]}, status=status.HTTP_409_CONFLICT)
        return Response(status=status.HTTP_204_NO_CONTENT)
