"""The CityCare network as the public sees it (B19): which hospitals belong to it, how their emergency
departments are doing, and what is available, as levels rather than exact stock.

Nothing here identifies a patient. Doctors' names go only to signed-in hospital staff (#122, B13 finding F5);
the public sees specialties and counts. Each read is a fixed number of queries, whatever the size of the
network.
"""

from django.db.models import Count, Max, Q
from django.utils import timezone

from apps.ambulances.models import Ambulance, AmbulanceStatus
from apps.blood.models import BloodGroup, BloodUnit, Component, UnitStatus
from apps.blood.services import RED_CELL_MINIMUM, stock_level
from apps.hospitals.models import Bed, BedStatus, BedType, Hospital
from apps.specialists.models import Specialist

from .models import EmergencyStatus, ErStatus

# A bed type counts as "available" while at least this share of its beds in service is free.
AVAILABLE_SHARE = 0.15


def availability(free: int, total: int) -> str | None:
    """'available', 'limited' or 'full' for `free` of `total` beds in service, or None when there are none."""
    if total <= 0:
        return None
    if free >= max(1, total * AVAILABLE_SHARE):
        return "available"
    if free > 0:
        return "limited"
    return "full"


def _bed_rows(hospital=None):
    beds = Bed.objects.filter(hospital__is_active=True).exclude(status=BedStatus.OUT_OF_SERVICE)
    if hospital is not None:
        beds = beds.filter(hospital=hospital)
    return (
        beds.values("bed_type")
        .annotate(total=Count("id"), free=Count("id", filter=Q(status=BedStatus.FREE)))
        .order_by()
    )


def bed_levels(hospital=None) -> list[dict]:
    """[{bedType, level}] in BedType order, for one hospital or (None) the whole network. Types it has no beds
    of
    are left out."""
    by_type = {row["bed_type"]: row for row in _bed_rows(hospital)}
    levels = []
    for bed_type in BedType.values:
        row = by_type.get(bed_type)
        level = availability(row["free"], row["total"]) if row else None
        if level is not None:
            levels.append({"bedType": bed_type, "level": level})
    return levels


def blood_levels(now) -> list[dict]:
    """[{group, level}] for red cells across the network: usable units against the command centre's minimum
    for
    each group (RED_CELL_MINIMUM), times the number of hospitals that keep blood. Empty when none does."""
    active = BloodUnit.objects.filter(hospital__is_active=True)
    keepers = active.values("hospital_id").distinct().count()
    if keepers == 0:
        return []
    usable = dict(
        active.filter(component=Component.RED_CELLS, status=UnitStatus.AVAILABLE, expires_at__gt=now)
        .values_list("group")
        .annotate(n=Count("id"))
        .order_by()
    )
    return [
        {"group": group, "level": stock_level(usable.get(group, 0), RED_CELL_MINIMUM[group] * keepers)}
        for group in BloodGroup.values
    ]


def emergency_data(status: EmergencyStatus | None) -> dict | None:
    if status is None:
        return None
    return {
        "status": status.status,
        "waitMinutes": status.wait_minutes,
        "waitingCount": status.waiting_count,
        "updatedAt": status.updated_at.isoformat(),
    }


def _active_hospitals():
    return Hospital.objects.filter(is_active=True).select_related("emergency_status")


def _status_of(hospital) -> EmergencyStatus | None:
    try:
        return hospital.emergency_status
    except EmergencyStatus.DoesNotExist:
        return None


def network_snapshot(now=None) -> dict:
    """The city at a glance: shape of `NetworkSnapshot` in frontend/src/api/public.ts."""
    now = now or timezone.now()
    hospitals = list(_active_hospitals())
    counts = {value: 0 for value in ErStatus.values}
    not_reported = 0
    shortest = None
    for hospital in hospitals:
        status = _status_of(hospital)
        if status is None:
            not_reported += 1
            continue
        counts[status.status] += 1
        if status.status != ErStatus.DIVERTING and (shortest is None or status.wait_minutes < shortest[1]):
            shortest = (hospital, status.wait_minutes)
    ambulances = Ambulance.objects.filter(hospital__is_active=True).exclude(
        status=AmbulanceStatus.OUT_OF_SERVICE
    )
    fleet = ambulances.aggregate(
        total=Count("id"), available=Count("id", filter=Q(status=AmbulanceStatus.AVAILABLE))
    )
    latest = EmergencyStatus.objects.filter(hospital__is_active=True).aggregate(at=Max("updated_at"))["at"]
    return {
        "updatedAt": (latest or now).isoformat(),
        "hospitals": len(hospitals),
        "emergency": {
            **counts,
            "notReported": not_reported,
            "shortestWait": None
            if shortest is None
            else {"hospitalId": shortest[0].pk, "name": shortest[0].name, "waitMinutes": shortest[1]},
        },
        "beds": bed_levels(),
        "blood": blood_levels(now),
        "ambulances": {"available": fleet["available"], "total": fleet["total"]},
    }


def _summary(hospital) -> dict:
    return {
        "id": hospital.pk,
        "name": hospital.name,
        "type": hospital.type,
        "address": hospital.address,
        "latitude": float(hospital.latitude),
        "longitude": float(hospital.longitude),
        "phone": hospital.phone,
        "services": [capability.name for capability in hospital.capabilities.all()],
        "emergency": emergency_data(_status_of(hospital)),
    }


def public_hospitals() -> list[dict]:
    """Every active hospital, by name: shape of `PublicHospital` in frontend/src/api/public.ts."""
    return [_summary(h) for h in _active_hospitals().prefetch_related("capabilities").order_by("name")]


def public_hospital(pk: int):
    """The active hospital with this id, or None."""
    return _active_hospitals().prefetch_related("capabilities", "departments").filter(pk=pk).first()


def hospital_profile(hospital, *, show_names: bool, now=None) -> dict:
    """One hospital's public page: shape of `PublicHospitalDetail` in frontend/src/api/public.ts. On duty
    means a
    specialist on call right now (B16), grouped by specialty; names only when `show_names`."""
    now = now or timezone.now()
    on_call = Specialist.objects.filter(hospital=hospital).available_at(now).order_by("specialty", "name")
    groups: dict[str, list[str]] = {}
    for specialist in on_call:
        groups.setdefault(specialist.specialty, []).append(specialist.name)
    return {
        **_summary(hospital),
        "departments": [department.name for department in hospital.departments.all()],
        "beds": bed_levels(hospital),
        "onDuty": [
            {"specialty": specialty, "count": len(names), "names": names if show_names else None}
            for specialty, names in groups.items()
        ],
        "namesShown": show_names,
    }
