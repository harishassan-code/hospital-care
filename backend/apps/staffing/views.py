"""Staff on duty (B22): who is on duty at the user's hospital now against the rota, who hasn't come in, and
whether each department has enough nurses for its patients. Actions: clock someone in, or mark them absent."""

from collections import Counter, defaultdict
from datetime import datetime, time, timedelta

from django.http import Http404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import can_edit, module_permission
from apps.core import clock
from apps.hospitals.models import BedStatus, BedType, Ward

from .models import Shift, StaffRole
from .services import clock_in, mark_absent

# Patients per nurse a department should not exceed, by the kind of bed most of its patients are in.
TARGET_RATIO = {BedType.ICU: 2, BedType.NICU: 2, BedType.EMERGENCY: 4}
WARD_TARGET = 8
EXPECTED_WITHIN = timedelta(minutes=45)  # someone not in this long after their start counts as missing


def shift_status(shift: Shift, now) -> str:
    if shift.absent:
        return "absent"
    if shift.clocked_out_at is not None and shift.clocked_out_at <= now:
        return "finished"
    if shift.clocked_in_at is not None and shift.clocked_in_at <= now:
        return "late" if shift.clocked_in_at - shift.starts_at > timedelta(minutes=10) else "onDuty"
    if shift.starts_at > now:
        return "upcoming"
    return "missing" if now - shift.starts_at > EXPECTED_WITHIN else "notInYet"


def shift_actions(shift: Shift, state: str, editable: bool) -> list[str]:
    if not editable:
        return []
    if state in ("notInYet", "missing"):
        return ["clockIn", "markAbsent"]
    if state == "upcoming" and shift.starts_at - timedelta(minutes=30) <= clock.now():
        return ["clockIn"]
    return []


def shift_data(shift: Shift, now, editable: bool) -> dict:
    state = shift_status(shift, now)
    return {
        "id": shift.pk,
        "name": shift.staff.name,
        "role": shift.staff.role,
        "department": shift.staff.department,
        "startsAt": shift.starts_at,
        "endsAt": shift.ends_at,
        "clockedInAt": shift.clocked_in_at,
        "clockedOutAt": shift.clocked_out_at,
        "status": state,
        "actions": shift_actions(shift, state, editable),
    }


def _hospital(request):
    if request.user.hospital_id is None:
        raise Http404("You aren't attached to a hospital.")
    return request.user.hospital


def day_curve(hospital, now) -> list[dict]:
    """Today's hours: doctors and nurses planned, and on duty (for hours that have started)."""
    start = timezone.make_aware(datetime.combine(timezone.localdate(now), time(0)))
    shifts = list(
        Shift.objects.filter(hospital=hospital, starts_at__lt=start + timedelta(days=1), ends_at__gt=start)
        .select_related("staff")
        .only("starts_at", "ends_at", "clocked_in_at", "clocked_out_at", "absent", "staff__role")
    )
    out = []
    for hour in range(24):
        at = start + timedelta(hours=hour, minutes=30)
        planned, present = Counter(), Counter()
        for s in shifts:
            if s.starts_at <= at < s.ends_at:
                planned[s.staff.role] += 1
            if (
                s.clocked_in_at
                and s.clocked_in_at <= at
                and (s.clocked_out_at is None or s.clocked_out_at > at)
            ):
                present[s.staff.role] += 1
        row = {"hour": hour, "plannedDoctors": planned["doctor"], "plannedNurses": planned["nurse"]}
        if at <= now:
            row.update(doctors=present["doctor"], nurses=present["nurse"])
        out.append(row)
    return out


def ratios(hospital, now) -> list[dict]:
    """Per department: patients in its beds, nurses on duty, patients per nurse, and the ratio to keep."""
    patients: Counter = Counter()
    kinds: dict = defaultdict(Counter)
    for ward in Ward.objects.filter(hospital=hospital).select_related("department"):
        name = ward.department.name if ward.department else "General medicine"
        for bed_type, bed_status in ward.beds.values_list("bed_type", "status"):
            kinds[name][bed_type] += 1
            if bed_status == BedStatus.OCCUPIED:
                patients[name] += 1
    nurses = Counter(
        Shift.objects.filter(hospital=hospital, staff__role=StaffRole.NURSE)
        .on_duty_at(now)
        .values_list("staff__department", flat=True)
    )
    rows = []
    for department in sorted(kinds):
        main_kind = kinds[department].most_common(1)[0][0]
        target = TARGET_RATIO.get(main_kind, WARD_TARGET)
        n = nurses[department]
        per_nurse = round(patients[department] / n, 1) if n else None
        rows.append(
            {
                "department": department,
                "patients": patients[department],
                "nurses": n,
                "patientsPerNurse": per_nurse,
                "target": target,
                "short": (n == 0 and patients[department] > 0) or (per_nurse or 0) > target,
            }
        )
    return rows


class StaffingView(APIView):
    """GET /api/staffing/: on duty now against the rota, everyone due in now or within two hours, today's
    curve, and nurse-to-patient ratios by department."""

    permission_classes = [module_permission("staffing")]

    def get(self, request):
        hospital = _hospital(request)
        now = clock.now()
        editable = can_edit(request.user.effective_role, "staffing")
        shifts = (
            Shift.objects.filter(hospital=hospital, starts_at__lte=now + timedelta(hours=2), ends_at__gt=now)
            .select_related("staff")
            .order_by("staff__department", "staff__role", "starts_at", "staff__name")
        )
        people = [shift_data(s, now, editable) for s in shifts]
        current = [p for p in people if p["status"] != "upcoming"]
        summary = {
            role: {
                "planned": sum(1 for p in current if p["role"] == role),
                "onDuty": sum(1 for p in current if p["role"] == role and p["status"] in ("onDuty", "late")),
                "missing": sum(
                    1 for p in current if p["role"] == role and p["status"] in ("missing", "absent")
                ),
            }
            for role in StaffRole.values
        }
        return Response(
            {
                "now": now,
                "summary": summary,
                "people": people,
                "day": day_curve(hospital, now),
                "ratios": ratios(hospital, now),
            }
        )


class ShiftActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["clockIn", "markAbsent"])


class ShiftActionView(APIView):
    """POST /api/staffing/shifts/<id>/actions/ {action}: clock in (they arrived) or mark absent. Audit-logged.
    Another hospital's shift is a 404; a move the shift's state doesn't allow, a 409."""

    permission_classes = [module_permission("staffing")]

    def post(self, request, pk: int):
        hospital = _hospital(request)
        shift = Shift.objects.filter(pk=pk, hospital=hospital).select_related("staff").first()
        if shift is None:
            raise Http404("No shift with that id at your hospital.")
        data = ShiftActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        now = clock.now()
        action = data.validated_data["action"]
        if action not in shift_actions(shift, shift_status(shift, now), editable=True):
            return Response(
                {"detail": "That can't be done for this shift now."}, status=status.HTTP_409_CONFLICT
            )
        if action == "clockIn":
            clock_in(shift, at=now, actor=request.user)
        else:
            mark_absent(shift, actor=request.user)
        shift.refresh_from_db()
        return Response(shift_data(shift, now, editable=True))
