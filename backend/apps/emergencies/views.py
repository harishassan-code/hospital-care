from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.hospitals.models import DoctorShift
from apps.hospitals.serializers import DoctorSerializer

from .models import EmergencyStatus


class PublicStatusView(APIView):
    """GET /api/public/status/, no sign-in needed. Shape of `PublicStatus` in api/publicStatus.ts."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        er = EmergencyStatus.current()
        doctors = DoctorShift.objects.filter(is_active=True)
        return Response(
            {
                "updatedAt": er.updated_at.isoformat(),
                "emergency": {
                    "status": er.status,
                    "waitMinutes": er.wait_minutes,
                    "waitingCount": er.waiting_count,
                },
                "doctors": DoctorSerializer(doctors, many=True).data,
            }
        )
