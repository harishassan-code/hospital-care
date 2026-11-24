"""Writing the hourly figures as the city runs (B21): what was true at the end of each hour, and what happened
during it. The two weeks before come from the seed (B20)."""

from django.db.models import Count, Q

from apps.ambulances.models import Ambulance, AmbulanceStatus
from apps.blood.models import BloodUnit, Component, UnitStatus
from apps.emergencies.models import EmergencyStatus
from apps.equipment.models import Equipment, EquipmentStatus, EquipmentType
from apps.hospitals.models import Bed, BedStatus
from apps.operating_rooms.models import OperatingRoom, OrStatus
from apps.staffing.models import Shift

from . import catalog
from .models import MetricSnapshot


def levels(hospital, at) -> dict[str, float]:
    """The hospital's levels now (at the end of an hour)."""
    values: dict[str, float] = {}
    beds = (
        Bed.objects.filter(hospital=hospital)
        .values("bed_type")
        .annotate(
            in_service=Count("id", filter=~Q(status=BedStatus.OUT_OF_SERVICE)),
            occupied=Count("id", filter=Q(status=BedStatus.OCCUPIED)),
        )
    )
    for row in beds:
        if row["in_service"]:
            values[catalog.beds_occupied(row["bed_type"])] = row["occupied"]
            values[catalog.beds_in_service(row["bed_type"])] = row["in_service"]
    status = EmergencyStatus.objects.filter(hospital=hospital).first()
    if status is not None:
        values[catalog.ER_WAITING] = status.waiting_count
        values[catalog.ER_WAIT_MINUTES] = status.wait_minutes
    if BloodUnit.objects.filter(hospital=hospital).exists():
        values[catalog.BLOOD_RED_CELLS] = BloodUnit.objects.filter(
            hospital=hospital, component=Component.RED_CELLS, status=UnitStatus.AVAILABLE, expires_at__gt=at
        ).count()
    rooms = OperatingRoom.objects.filter(hospital=hospital).exclude(status=OrStatus.OUT_OF_SERVICE)
    if rooms.exists():
        values[catalog.OR_ROOMS] = rooms.count()
        values[catalog.OR_IN_USE] = rooms.filter(status=OrStatus.IN_USE).count()
    ventilators = Equipment.objects.filter(hospital=hospital, equipment_type=EquipmentType.VENTILATOR)
    if ventilators.exists():
        values[catalog.VENTILATORS_IN_USE] = ventilators.filter(status=EquipmentStatus.IN_USE).count()
    on_duty = (
        Shift.objects.filter(hospital=hospital).on_duty_at(at).values("staff__role").annotate(n=Count("id"))
    )
    for row in on_duty:
        values[catalog.staff_on_duty(row["staff__role"])] = row["n"]
    return values


def has_fleet(hospital) -> int:
    return Ambulance.objects.filter(hospital=hospital).exclude(status=AmbulanceStatus.OUT_OF_SERVICE).count()


def write_hour(hospital, hour_start, values: dict[str, float]) -> int:
    """Store one hour's figures; an hour already written is left as it is."""
    rows = [MetricSnapshot(hospital=hospital, metric=m, at=hour_start, value=v) for m, v in values.items()]
    MetricSnapshot.objects.bulk_create(rows, ignore_conflicts=True)
    return len(rows)
