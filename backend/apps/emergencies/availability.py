"""Local availability (story #33): what a case's own hospital has for each requirement, and what is still
short.

Worked out on read and never stored, because stock changes all the time. "Local" is the case's hospital.
Blood counts exact group and component matches only: cross-group compatibility (O- for anyone) is story #37.
"""

from dataclasses import dataclass

from django.db.models import Count, Q

from apps.blood.models import BloodUnit
from apps.blood.services import usable_units
from apps.equipment.models import Equipment
from apps.hospitals.models import Bed, BedStatus
from apps.matching.models import ReservationStatus
from apps.operating_rooms.models import OperatingRoom

from .models import EmergencyRequest, RequestItem, ResourceType


@dataclass(frozen=True)
class ItemAvailability:
    item: RequestItem
    available: int  # what the case's hospital has that matches this requirement exactly, free of holds
    shortfall: (
        int  # still needed from other hospitals: what is left of the need after its holds, less available
    )
    held: int = 0  # the need's resources held for this case (story #43), not yet allocated


@dataclass
class _Stock:
    """What the case's hospital has, before any line claims it. Counts for the countable kinds; for operating
    rooms, the usable rooms by id with their capabilities, because one room can serve two capabilities."""

    counts: dict[tuple, int]
    rooms: list[tuple[int, frozenset[str]]]


def local_availability(case: EmergencyRequest) -> list[ItemAvailability]:
    """One row per need, in the order of `case.items`. One grouped query per resource type, however many. A
    case with no hospital has 0 available for everything.

    A need's holds (story #43) come off its quantity before its shortfall is worked out: units held for
    this case are already its, so they aren't asked for from other hospitals. Held stock is not free, so it
    is not in `available` either. The holds are counted in the same query as the items.

    Needs that draw on the same stock (two O- blood lines, two ICU lines) share it in list order: the first
    sees the whole stock and the next sees what is left. Otherwise two lines could both claim the same
    units and the shortfall would be undercounted. An operating room is claimed by id, so a room that has
    two capabilities covers one line, not both."""
    items = list(
        case.items.annotate(
            held=Count("reservations", filter=Q(reservations__status=ReservationStatus.HELD)),
        ).order_by("id")
    )
    if not items:
        return []
    stock = _local_stock(case.hospital_id) if case.hospital_id else _Stock({}, [])
    counts, rooms = stock.counts, stock.rooms
    rows = []
    for item in items:
        # An allocated hold is already in fulfilled (story #45), so only the held ones come off here.
        need = max(0, item.quantity - item.fulfilled - item.held)
        if item.resource_type == ResourceType.OPERATING_ROOM:
            matching = [room for room in rooms if item.capability in room[1]]
            available = len(matching)
            claimed = {room_id for room_id, _ in matching[:need]}
            rooms = [room for room in rooms if room[0] not in claimed]
        else:
            key = _stock_key(item)
            available = counts.get(key, 0)
            counts[key] = available - min(available, need)
        shortfall = max(0, need - available)
        rows.append(ItemAvailability(item=item, available=available, shortfall=shortfall, held=item.held))
    return rows


def shortfall_items(case: EmergencyRequest) -> list[tuple[RequestItem, int]]:
    """Only the needs the case's hospital cannot cover, as (item, shortfall), in item order.

    This is the input to the matching step (#38), which asks other hospitals for these shortfalls and no more.
    """
    return [(row.item, row.shortfall) for row in local_availability(case) if row.shortfall > 0]


def _stock_key(item: RequestItem) -> tuple:
    if item.resource_type == ResourceType.BLOOD:
        return ("blood", item.blood_group, item.component)
    if item.resource_type == ResourceType.EQUIPMENT:
        return ("equipment", item.equipment_type)
    if item.resource_type == ResourceType.OPERATING_ROOM:
        return ("operatingRoom", item.capability)
    return ("bed", item.bed_type)


def _local_stock(hospital_id: int) -> _Stock:
    """Usable blood units, free beds, matchable equipment by type and matchable rooms, at one hospital: one
    query each. Blood is exact match only; the compatibility rules are story #37's."""
    blood = (
        usable_units(BloodUnit.objects.filter(hospital_id=hospital_id))
        .values("group", "component")
        .annotate(n=Count("id"))
        .order_by()
    )
    beds = (
        Bed.objects.filter(hospital_id=hospital_id, status=BedStatus.FREE)
        .values("bed_type")
        .annotate(n=Count("id"))
        .order_by()
    )
    equipment = (
        Equipment.objects.matchable()
        .filter(hospital_id=hospital_id)
        .values("equipment_type")
        .annotate(n=Count("id"))
        .order_by()
    )
    # ponytail: one query listing the hospital's rooms, not a grouped count, because a room's capabilities
    # are a JSON list. Fine at per-hospital room counts.
    rooms = (
        OperatingRoom.objects.matchable()
        .filter(hospital_id=hospital_id)
        .order_by("id")
        .values_list("id", "capabilities")
    )
    counts = {
        **{("blood", row["group"], row["component"]): row["n"] for row in blood},
        **{("bed", row["bed_type"]): row["n"] for row in beds},
        **{("equipment", row["equipment_type"]): row["n"] for row in equipment},
    }
    return _Stock(counts, [(room_id, frozenset(codes)) for room_id, codes in rooms])
