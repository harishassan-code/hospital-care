"""City command centre (story #55): the whole network's figures in one read, for admins.

Each figure is one grouped query over the active hospitals, so the number of queries is fixed whatever the
number of hospitals (tests/test_query_budget.py pins it). Rows are assembled in Python. Counts and names only:
no patient, case, unit or asset identifiers. Reads run the request-time sweeps first (see views.py).
"""

from datetime import timedelta

from django.conf import settings
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from apps.blood.models import BloodGroup, BloodUnit, Component, UnitStatus
from apps.blood.services import RED_CELL_MINIMUM, stock_level
from apps.emergencies.models import EmergencyRequest, RequestItem, RequestStatus, ResourceType
from apps.emergencies.services import ACTIVE
from apps.equipment.models import Equipment, EquipmentType
from apps.hospitals.models import Bed, BedStatus, BedType, Hospital
from apps.matching.models import Reservation, ReservationStatus
from apps.operating_rooms.models import OperatingRoom

# What the command centre counts as an active case: the network feed's set (story #36), escalated included.
ACTIVE_CASE_STATUSES = (*ACTIVE, RequestStatus.ESCALATED)


def _tally(rows, field: str) -> dict[int, dict[str, int]]:
    """{hospital id: {value of `field`: count}} from grouped rows that carry hospital_id and n."""
    out: dict[int, dict[str, int]] = {}
    for row in rows:
        out.setdefault(row["hospital_id"], {})[row[field]] = row["n"]
    return out


def _blood(now, soon) -> dict[int, dict[tuple[str, str], tuple[int, int]]]:
    """Usable units and the usable ones expiring by `soon`, per hospital, group and component.
    Usable is available and not yet expired, as usable_units() counts it."""
    usable = Q(status=UnitStatus.AVAILABLE, expires_at__gt=now)
    rows = (
        BloodUnit.objects.filter(hospital__is_active=True)
        .values("hospital_id", "group", "component")
        .annotate(
            usable=Count("id", filter=usable), near=Count("id", filter=usable & Q(expires_at__lte=soon))
        )
        .order_by()
    )
    out: dict[int, dict[tuple[str, str], tuple[int, int]]] = {}
    for row in rows:
        out.setdefault(row["hospital_id"], {})[(row["group"], row["component"])] = (
            row["usable"],
            row["near"],
        )
    return out


def _open_needs() -> dict[int, dict[str, int]]:
    """Per hospital and resource type, the need still open across its active cases: quantity less
    fulfilled less the holds held right now. Allocated holds are already in fulfilled, so they are not
    taken off twice."""
    held_now = (
        Reservation.objects.filter(request_item=OuterRef("pk"), status=ReservationStatus.HELD)
        .values("request_item")
        .annotate(n=Count("id"))
        .values("n")
    )
    rows = (
        RequestItem.objects.filter(
            request__status__in=ACTIVE_CASE_STATUSES, request__hospital__is_active=True
        )
        .annotate(held=Coalesce(Subquery(held_now, output_field=IntegerField()), Value(0)))
        .annotate(open_qty=Greatest(F("quantity") - F("fulfilled") - F("held"), Value(0)))
        .values(hospital_id=F("request__hospital_id"), kind=F("resource_type"))
        .annotate(total=Sum("open_qty"))
        .order_by()
    )
    out: dict[int, dict[str, int]] = {}
    for row in rows:
        out.setdefault(row["hospital_id"], {})[row["kind"]] = row["total"]
    return out


def _cases() -> dict[int, dict[str, int]]:
    rows = (
        EmergencyRequest.objects.filter(status__in=ACTIVE_CASE_STATUSES, hospital__is_active=True)
        .values("hospital_id")
        .annotate(active=Count("id"), escalated=Count("id", filter=Q(status=RequestStatus.ESCALATED)))
        .order_by()
    )
    return {row["hospital_id"]: {"active": row["active"], "escalated": row["escalated"]} for row in rows}


def _filled(counts: dict[str, int], keys) -> dict[str, int]:
    """The counts for every key, zero where a hospital has none."""
    return {key: counts.get(key, 0) for key in keys}


def _components(stock: dict[tuple[str, str], tuple[int, int]]) -> dict[str, dict[str, int]]:
    out = {}
    for component in Component.values:
        usable = [stock.get((group, component), (0, 0)) for group in BloodGroup.values]
        out[component] = {
            "usable": sum(u for u, _ in usable),
            "nearExpiry": sum(n for _, n in usable),
        }
    return out


def _totals(hospitals: list[dict]) -> dict:
    """The network totals: sums of the hospital rows. Zero for an empty network, and never a level."""

    def sum_of(getter, keys) -> dict[str, int]:
        return {key: sum(getter(h)[key] for h in hospitals) for key in keys}

    return {
        "redCells": [
            {"group": group, "available": sum(h["redCells"][i]["available"] for h in hospitals)}
            for i, group in enumerate(BloodGroup.values)
        ],
        "components": {
            component: {
                field: sum(h["components"][component][field] for h in hospitals)
                for field in ("usable", "nearExpiry")
            }
            for component in Component.values
        },
        "beds": sum_of(lambda h: h["beds"], BedType.values),
        "equipment": sum_of(lambda h: h["equipment"], EquipmentType.values),
        "operatingRooms": sum(h["operatingRooms"] for h in hospitals),
        "cases": sum_of(lambda h: h["cases"], ("active", "escalated")),
        "open": sum_of(lambda h: h["open"], ResourceType.values),
    }


def network_figures(now=None) -> dict:
    now = now or timezone.now()
    soon = now + timedelta(days=settings.BLOOD_NEAR_EXPIRY_DAYS)
    names = dict(Hospital.objects.filter(is_active=True).values_list("id", "name"))

    blood = _blood(now, soon)
    beds = _tally(
        Bed.objects.filter(hospital__is_active=True, status=BedStatus.FREE)
        .values("hospital_id", "bed_type")
        .annotate(n=Count("id"))
        .order_by(),
        "bed_type",
    )
    equipment = _tally(
        Equipment.objects.matchable()
        .filter(hospital__is_active=True)
        .values("hospital_id", "equipment_type")
        .annotate(n=Count("id"))
        .order_by(),
        "equipment_type",
    )
    rooms = {
        row["hospital_id"]: row["n"]
        for row in OperatingRoom.objects.matchable()
        .filter(hospital__is_active=True)
        .values("hospital_id")
        .annotate(n=Count("id"))
        .order_by()
    }
    cases = _cases()
    open_needs = _open_needs()

    hospitals = []
    for hospital_id, name in names.items():
        stock = blood.get(hospital_id, {})
        red_cells = []
        for group in BloodGroup.values:
            available = stock.get((group, Component.RED_CELLS), (0, 0))[0]
            minimum = RED_CELL_MINIMUM[group]
            red_cells.append(
                {
                    "group": group,
                    "available": available,
                    "minimum": minimum,
                    "level": stock_level(available, minimum),
                }
            )
        hospitals.append(
            {
                "id": hospital_id,
                "name": name,
                "redCells": red_cells,
                "components": _components(stock),
                "beds": _filled(beds.get(hospital_id, {}), BedType.values),
                "equipment": _filled(equipment.get(hospital_id, {}), EquipmentType.values),
                "operatingRooms": rooms.get(hospital_id, 0),
                "cases": cases.get(hospital_id, {"active": 0, "escalated": 0}),
                "open": _filled(open_needs.get(hospital_id, {}), ResourceType.values),
            }
        )

    # Hospitals with a critical red-cell group first, then the rest by name.
    hospitals.sort(
        key=lambda h: (not any(r["level"] == "critical" for r in h["redCells"]), h["name"].casefold())
    )

    return {
        "updatedAt": now.isoformat(),
        "nearExpiryDays": settings.BLOOD_NEAR_EXPIRY_DAYS,
        "totals": _totals(hospitals),
        "hospitals": hospitals,
    }
