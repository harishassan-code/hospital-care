"""Labels and plain-data shapes that the API and the stored snapshots share (B17).

A patient transfer keeps the destination's #42 entry as it was when the transfer was requested. The services
that write that snapshot can't import the serializers (they import the services), so the shapes live here, and
the serializers delegate to them."""

from apps.blood.models import Component
from apps.equipment.models import EquipmentType
from apps.hospitals.models import BedType
from apps.matching.multi import HospitalMatch
from apps.operating_rooms.models import OrCapability

from .models import RequestItem, ResourceType


def need_label(item: RequestItem) -> str:
    """A requirement as a short label for the sources list: "O- red cells", "ICU bed", "Ventilator",
    "Cardiac operating room"."""
    if item.resource_type == ResourceType.BLOOD:
        return f"{item.blood_group} {Component(item.component).label.lower()}"
    if item.resource_type == ResourceType.BED:
        return f"{BedType(item.bed_type).label} bed"
    if item.resource_type == ResourceType.EQUIPMENT:
        return EquipmentType(item.equipment_type).label
    return f"{OrCapability(item.capability).label} operating room"


def hospital_match_data(match: HospitalMatch) -> dict:
    """One hospital judged across the case's short needs (story #42), as the API shows it. `recommended` is
    true only on rank 1, and only when that hospital has everything. Plain data: it can be stored as JSON."""
    return {
        "rank": match.rank,
        "hospital": {"id": match.hospital.pk, "name": match.hospital.name},
        "complete": match.complete,
        "recommended": match.rank == 1 and match.complete,
        "coverage": f"{len(match.covered)} of {match.total_needs}",
        "coveredCount": len(match.covered),
        "totalNeeds": match.total_needs,
        "score": match.score,
        "distanceKm": None if match.distance_km is None else round(match.distance_km, 1),
        "travelMinutes": match.travel_minutes,
        "covered": [{"itemId": m.item.pk, "need": need_label(m.item)} for m in match.covered],
        "unmet": [
            {
                "itemId": m.item.pk,
                "need": need_label(m.item),
                "missing": m.missing,
                "available": m.available,
            }
            for m in match.unmet
        ],
    }
