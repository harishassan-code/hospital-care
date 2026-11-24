"""The emergency department queue (B22): the user's own hospital's patients who are waiting, being treated or
waiting for a ward bed, and what staff can do next with each. Patients are shown by a random tag, age band,
sex, complaint category and triage level only, never a name (B23: the minimum necessary)."""

from datetime import timedelta

from django.http import Http404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import can_edit, module_permission
from apps.core import clock
from apps.hospitals.models import Bed, BedStatus, BedType
from apps.resources.state_machine import TransitionNotAllowed

from .department import department_status
from .models import ErVisit, VisitStatus
from .serializers import DepartmentStatusSerializer
from .visits import STAFF_ACTIONS, NoBedFree, actions_for, staff_action

OPEN = (VisitStatus.WAITING, VisitStatus.TREATING, VisitStatus.BOARDING)
HOUR = timedelta(hours=1)


def visit_data(visit: ErVisit, now, *, can_act: bool) -> dict:
    waited_until = visit.seen_at or now
    return {
        "id": visit.pk,
        "tag": visit.tag,
        "triage": visit.triage,
        "ageBand": visit.age_band,
        "sex": visit.sex,
        "complaint": visit.complaint,
        "complaintLabel": visit.get_complaint_display(),
        "status": visit.status,
        "arrivedAt": visit.arrived_at,
        "seenAt": visit.seen_at,
        "dueAt": visit.due_at,
        "waitedMinutes": max(0, round((waited_until - visit.arrived_at).total_seconds() / 60)),
        "bed": visit.bed.label if visit.bed_id else None,
        "handledByStaff": visit.handled_by_id is not None,
        "actions": actions_for(visit) if can_act else [],
    }


def _hospital(request):
    if request.user.hospital_id is None:
        raise Http404("You aren't attached to a hospital.")
    return request.user.hospital


class QueueView(APIView):
    """GET /api/emergencies/queue/: the queue, the department's status and its beds."""

    permission_classes = [module_permission("emergencyDepartment")]

    def get(self, request):
        hospital = _hospital(request)
        now = clock.now()
        visits = ErVisit.objects.filter(hospital=hospital, status__in=OPEN).select_related("bed")
        can_act = can_edit(request.user.effective_role, "emergencyDepartment")
        beds = Bed.objects.filter(hospital=hospital, bed_type=BedType.EMERGENCY).exclude(
            status=BedStatus.OUT_OF_SERVICE
        )
        current = department_status(hospital)
        return Response(
            {
                "visits": [visit_data(v, now, can_act=can_act) for v in visits],
                "department": DepartmentStatusSerializer(current).data if current else None,
                "beds": {"total": beds.count(), "free": beds.filter(status=BedStatus.FREE).count()},
                "seenLastHour": ErVisit.objects.filter(hospital=hospital, seen_at__gt=now - HOUR).count(),
                "now": now,
            }
        )


class QueueActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=STAFF_ACTIONS)


class QueueActionView(APIView):
    """POST /api/emergencies/queue/<id>/actions/ {action}: start treatment, discharge, admit, transfer, or
    left unseen. Another hospital's patient is a 404; a move the visit's state doesn't allow, or no bed free,
    a 409."""

    permission_classes = [module_permission("emergencyDepartment")]

    def post(self, request, pk: int):
        hospital = _hospital(request)
        visit = ErVisit.objects.filter(pk=pk, hospital=hospital).first()
        if visit is None:
            raise Http404("No patient with that id in your department.")
        data = QueueActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            visit = staff_action(visit, data.validated_data["action"], actor=request.user)
        except (TransitionNotAllowed, NoBedFree) as error:
            return Response({"detail": str(error)}, status=status.HTTP_409_CONFLICT)
        visit = ErVisit.objects.select_related("bed").get(pk=visit.pk)
        return Response(visit_data(visit, clock.now(), can_act=True))
