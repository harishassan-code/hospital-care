"""The signed-in user's own emergency department status (B19)."""

from django.http import Http404
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission

from .department import department_status, update_department_status
from .serializers import DepartmentStatusSerializer

NOT_REPORTED = {
    "status": None,
    "waitMinutes": None,
    "waitingCount": None,
    "updatedAt": None,
    "factors": [],
    "setBySimulation": False,
}


class DepartmentStatusView(APIView):
    """GET/PUT /api/emergencies/department/. Reading needs the emergencies module, changing it edit rights
    (admin, doctor, nurse). It is always the user's own hospital; staff with no hospital have no department
    (404). A hospital that hasn't reported yet reads as all nulls. On staging the simulation sets it, with the
    factors behind the wait (B21); a person's own setting has none."""

    permission_classes = [module_permission("emergencies")]

    @staticmethod
    def _hospital(request):
        if request.user.hospital_id is None:
            raise Http404("You aren't attached to a hospital.")
        return request.user.hospital

    def get(self, request):
        status = department_status(self._hospital(request))
        return Response(NOT_REPORTED if status is None else DepartmentStatusSerializer(status).data)

    def put(self, request):
        hospital = self._hospital(request)
        serializer = DepartmentStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status = update_department_status(hospital=hospital, actor=request.user, **serializer.validated_data)
        return Response(DepartmentStatusSerializer(status).data)
