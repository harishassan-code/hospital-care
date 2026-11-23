from django.db.models import Prefetch
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission, own_hospital

from .models import Batch, Medicine
from .serializers import MedicineSerializer


class StockView(APIView):
    """GET /api/pharmacy/stock/ → every medicine in the shared formulary, with the batches the user's hospital
    holds (#123, B13 finding F7). Admins without a hospital see every hospital's batches."""

    permission_classes = [module_permission("pharmacy")]

    def get(self, request):
        batches = own_hospital(Batch.objects.all(), request.user)
        medicines = Medicine.objects.prefetch_related(Prefetch("batches", queryset=batches))
        return Response(MedicineSerializer(medicines, many=True).data)
