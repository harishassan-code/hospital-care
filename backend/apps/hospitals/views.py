from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission

from .models import Bed, Ward
from .serializers import BedActionSerializer, BedSerializer, WardSerializer
from .services import BedActionRefused, apply_bed_action


class BedBoardView(APIView):
    """GET /api/beds/ → {wards, beds}, the shape of `BedBoard` in frontend/src/api/beds.ts."""

    permission_classes = [module_permission("beds")]

    def get(self, request):
        wards = Ward.objects.all()
        beds = Bed.objects.select_related("ward")
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
            bed = apply_bed_action(label, serializer.validated_data["action"])
        except BedActionRefused as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(BedSerializer(bed).data)
