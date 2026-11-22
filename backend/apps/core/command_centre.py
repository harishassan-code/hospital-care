"""City command centre (story #55): the whole network on one page. A fixed number of grouped queries, however
many hospitals there are (pinned in apps/core/tests/test_command_centre.py)."""

from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.blood.models import BloodUnit, Component, UnitStatus
from apps.emergencies.models import EmergencyRequest, RequestStatus
from apps.equipment.models import Equipment, EquipmentStatus
from apps.hospitals.models import Bed, BedStatus, BedType, Hospital

# Red-cell par levels per group; the same numbers as MINIMUM_STOCK.redCells in frontend/src/api/blood.ts.
RED_CELL_MINIMUM = {"O-": 6, "O+": 30, "A-": 4, "A+": 20, "B-": 4, "B+": 30, "AB-": 2, "AB+": 8}
FINISHED = (RequestStatus.FULFILLED, RequestStatus.CLOSED, RequestStatus.CANCELLED)


def network_snapshot(now=None) -> dict:
    now = now or timezone.now()
    hospitals = {h.pk: h for h in Hospital.objects.order_by("name")}
    rows = {
        pk: {
            "id": pk,
            "name": h.name,
            "beds": {"free": 0, "total": 0},
            "icu": {"free": 0, "total": 0},
            "redCells": dict.fromkeys(RED_CELL_MINIMUM, 0),
            "nearExpiry": 0,
            "equipment": {"available": 0, "total": 0},
            "emergencies": defaultdict(int),
        }
        for pk, h in hospitals.items()
    }
    free = Q(status=BedStatus.FREE)
    for r in Bed.objects.values("hospital_id", "bed_type").annotate(
        total=Count("id"), free=Count("id", free)
    ):
        row = rows.get(r["hospital_id"])
        if row is None:
            continue
        row["beds"]["free"] += r["free"]
        row["beds"]["total"] += r["total"]
        if r["bed_type"] == BedType.ICU:
            row["icu"] = {"free": r["free"], "total": r["total"]}

    usable = BloodUnit.objects.filter(status=UnitStatus.AVAILABLE, expires_at__gt=now)
    for r in (
        usable.filter(component=Component.RED_CELLS).values("hospital_id", "group").annotate(n=Count("id"))
    ):
        if r["hospital_id"] in rows:
            rows[r["hospital_id"]]["redCells"][r["group"]] = r["n"]
    soon = usable.filter(expires_at__lte=now + timedelta(days=settings.BLOOD_NEAR_EXPIRY_DAYS))
    for r in soon.values("hospital_id").annotate(n=Count("id")):
        if r["hospital_id"] in rows:
            rows[r["hospital_id"]]["nearExpiry"] = r["n"]

    available = Q(status=EquipmentStatus.AVAILABLE)
    for r in Equipment.objects.values("hospital_id").annotate(
        total=Count("id"), available=Count("id", available)
    ):
        if r["hospital_id"] in rows:
            rows[r["hospital_id"]]["equipment"] = {"available": r["available"], "total": r["total"]}

    active = EmergencyRequest.objects.exclude(status__in=FINISHED)
    for r in active.values("hospital_id", "severity").annotate(n=Count("id")):
        if r["hospital_id"] in rows:
            rows[r["hospital_id"]]["emergencies"][r["severity"]] = r["n"]

    shortages = []
    for row in rows.values():
        row["emergencies"] = dict(row["emergencies"])
        for group, minimum in RED_CELL_MINIMUM.items():
            count = row["redCells"][group]
            if count < minimum:
                level = "critical" if count < minimum / 2 else "low"
                shortages.append(
                    {
                        "hospital": row["name"],
                        "kind": "blood",
                        "group": group,
                        "count": count,
                        "minimum": minimum,
                        "level": level,
                    }
                )
        if row["icu"]["total"] and row["icu"]["free"] == 0:
            shortages.append({"hospital": row["name"], "kind": "icu", "level": "critical"})

    hospitals_out = list(rows.values())
    totals = {
        "hospitals": len(hospitals_out),
        "freeBeds": sum(r["beds"]["free"] for r in hospitals_out),
        "freeIcu": sum(r["icu"]["free"] for r in hospitals_out),
        "redCells": sum(sum(r["redCells"].values()) for r in hospitals_out),
        "nearExpiry": sum(r["nearExpiry"] for r in hospitals_out),
        "activeEmergencies": sum(sum(r["emergencies"].values()) for r in hospitals_out),
    }
    return {"totals": totals, "hospitals": hospitals_out, "shortages": shortages}


class CommandCentreView(APIView):
    """GET /api/command-centre/ → network totals, one row per hospital and the shortages (admin only)."""

    permission_classes = [module_permission("commandCentre")]

    def get(self, request):
        return Response(network_snapshot())
