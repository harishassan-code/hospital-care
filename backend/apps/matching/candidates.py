"""Candidate hospitals (story #38): which other hospitals can supply a case's shortfall, and how far away
they are.

One registry maps each requirement type to the matchable resources that satisfy it, as a queryset of a
`Resource`
subclass. One generic query then groups them by hospital, because every subclass shares `Resource`'s hospital
foreign key. This module gives the plain order: covering first, then nearest, then id. The API ranks and
scores the candidates with `scoring.rank` (#40, shown in #41).
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from django.db.models import Count, Min, QuerySet

from apps.emergencies.availability import shortfall_items
from apps.emergencies.models import EmergencyRequest, RequestItem, ResourceType
from apps.equipment.models import Equipment
from apps.hospitals.models import Bed, BedStatus, Hospital
from apps.operating_rooms.models import OperatingRoom

from .compatibility import compatible_units
from .distance import estimated_travel_minutes, hospital_distance


def _blood(item: RequestItem) -> QuerySet:
    return compatible_units(item.blood_group, item.component)


def _beds(item: RequestItem) -> QuerySet:
    return Bed.objects.filter(status=BedStatus.FREE, bed_type=item.bed_type)


def _equipment(item: RequestItem) -> QuerySet:
    return Equipment.objects.matchable().filter(equipment_type=item.equipment_type)


def _rooms(item: RequestItem) -> QuerySet:
    return OperatingRoom.objects.matchable().with_capability(item.capability)


# One entry per requirement type: the matchable resources that satisfy one requirement of it.
REGISTRY: dict[str, Callable[[RequestItem], QuerySet]] = {
    ResourceType.BLOOD: _blood,
    ResourceType.BED: _beds,
    ResourceType.EQUIPMENT: _equipment,
    ResourceType.OPERATING_ROOM: _rooms,
}


@dataclass(frozen=True)
class Candidate:
    hospital: Hospital
    available: int  # matchable resources at this hospital for the requirement
    covers: bool  # available >= the shortfall
    distance_km: float | None  # None when the case has no hospital or either side has no coordinates
    travel_minutes: int | None  # #39's estimate, rounded; None with distance_km
    earliest_expiry: datetime | None = None  # blood only
    best_donor_rank: int | None = None  # blood only; 0 is the identical group


@dataclass(frozen=True)
class ItemCandidates:
    item: RequestItem
    shortfall: int
    candidates: list[Candidate]


def find_candidates(item: RequestItem, *, origin_hospital: Hospital | None, needed: int) -> list[Candidate]:
    """Other hospitals that can supply `needed` of this requirement, in the default order. One grouped
    query and
    one hospital fetch, whatever the number of hospitals."""
    rows = _grouped(item, origin_hospital)
    hospitals = Hospital.objects.in_bulk({row["hospital_id"] for row in rows})
    return _candidates(item, origin_hospital, rows, hospitals, needed)


def candidates_for_case(case: EmergencyRequest) -> list[ItemCandidates]:
    """For each requirement the case's hospital cannot cover, its candidates. Items with no shortfall are
    left out.
    One grouped query per short item, plus one hospital fetch for all the candidate hospitals together."""
    origin = case.hospital
    short = shortfall_items(case)
    grouped = [(item, shortfall, _grouped(item, origin)) for item, shortfall in short]
    hospitals = Hospital.objects.in_bulk({row["hospital_id"] for _, _, rows in grouped for row in rows})
    return [
        ItemCandidates(
            item=item,
            shortfall=shortfall,
            candidates=_candidates(item, origin, rows, hospitals, shortfall),
        )
        for item, shortfall, rows in grouped
    ]


def _grouped(item: RequestItem, origin: Hospital | None) -> list[dict]:
    """The generic part: matchable resources per hospital, leaving out the origin and inactive hospitals."""
    resources = REGISTRY[item.resource_type](item).filter(hospital__is_active=True)
    if origin is not None:
        resources = resources.exclude(hospital_id=origin.pk)
    aggregates = {"available": Count("id")}
    if item.resource_type == ResourceType.BLOOD:
        aggregates.update(earliest_expiry=Min("expires_at"), best_donor_rank=Min("donor_rank"))
    # order_by() clears the ordering that compatible_units sets, so it can't leak into the grouping.
    return list(resources.values("hospital_id").annotate(**aggregates).order_by())


def _candidates(
    item: RequestItem, origin: Hospital | None, rows: list[dict], hospitals: dict, needed: int
) -> list[Candidate]:
    found = []
    for row in rows:
        hospital = hospitals[row["hospital_id"]]
        km = _km_between(origin, hospital)
        found.append(
            Candidate(
                hospital=hospital,
                available=row["available"],
                covers=row["available"] >= needed,
                distance_km=km,
                travel_minutes=None if km is None else round(estimated_travel_minutes(km)),
                earliest_expiry=row.get("earliest_expiry"),
                best_donor_rank=row.get("best_donor_rank"),
            )
        )
    # Covering first, then nearest (no distance last), then hospital id.
    found.sort(key=lambda c: (not c.covers, c.distance_km is None, c.distance_km or 0.0, c.hospital.pk))
    return found


def _km_between(origin: Hospital | None, hospital: Hospital) -> float | None:
    if origin is None or None in (origin.latitude, origin.longitude, hospital.latitude, hospital.longitude):
        return None
    return hospital_distance(origin, hospital)
