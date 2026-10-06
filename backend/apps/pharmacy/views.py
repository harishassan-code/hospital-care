from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission

from .models import Medicine
from .serializers import MedicineSerializer


class StockView(APIView):
    """GET /api/pharmacy/stock/ → every medicine with its batches."""

    permission_classes = [module_permission("pharmacy")]

    def get(self, request):
        medicines = Medicine.objects.prefetch_related("batches")
        return Response(MedicineSerializer(medicines, many=True).data)
