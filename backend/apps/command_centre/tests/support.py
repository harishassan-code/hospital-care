"""Shared setup for the command centre tests: hospitals with stock, beds, equipment, rooms and cases."""

from django.conf import settings

from apps.blood.models import UnitStatus
from apps.blood.services import RED_CELL_MINIMUM
from apps.emergencies.models import RequestItem
from apps.equipment.models import EquipmentStatus
from apps.hospitals.models import BedStatus
from apps.matching.tests.reservation_support import (
    bed,
    bed_need,
    blood_need,
    case,
    equipment,
    hold,
    room,
    staff,
    unit,
)
from apps.operating_rooms.models import OrStatus


def stocked_hospital(hospital, make_user):
    """Civic General: one critical A- red cell, two usable red cells (one near expiry), one plasma, and
    units that must not count (reserved, expired, quarantined). Free and busy beds, equipment and rooms.
    Three cases: one open with a unit held, one escalated, and two no longer active."""
    nurse = staff(make_user, hospital)
    near = settings.BLOOD_NEAR_EXPIRY_DAYS
    unit(hospital, group="A-")  # usable, not near expiry
    unit(hospital, group="O+", expires_in_days=near - 1)  # usable, near expiry
    unit(hospital, group="A-", status=UnitStatus.RESERVED)  # held: not usable
    unit(hospital, group="A-", expires_in_days=-1)  # past expiry: not usable
    unit(hospital, group="A-", status=UnitStatus.QUARANTINED)  # not released yet: not usable
    unit(hospital, group="A+", component="plasma")  # usable plasma
    bed(hospital, "icu")
    bed(hospital, "icu")
    bed(hospital, "icu", status=BedStatus.RESERVED)  # held: not free
    bed(hospital, "general", status=BedStatus.OCCUPIED)
    bed(hospital, "isolation")
    equipment(hospital, "ventilator")
    equipment(hospital, "ventilator", status=EquipmentStatus.IN_USE)
    equipment(hospital, "monitor")
    equipment(hospital, "defibrillator", status=EquipmentStatus.MAINTENANCE)
    room(hospital)
    room(hospital, status=OrStatus.IN_USE)

    # Open: 5 needed, 1 fulfilled, 1 held right now, so 3 still open.
    open_case = case(hospital, blood_need("A-", quantity=5, fulfilled=1), status="matching")
    held_unit = unit(hospital, group="A-", status=UnitStatus.RESERVED)
    hold(RequestItem.objects.get(request=open_case), held_unit, hospital=hospital, actor=nurse)
    # Escalated: two ICU beds still wanted.
    case(hospital, bed_need("icu", quantity=2), status="escalated", severity="critical")
    # No longer active: neither counts, nor their open needs.
    case(hospital, blood_need("O+", quantity=9), status="fulfilled")
    case(hospital, blood_need("O+", quantity=9), status="closed")
    return nurse


def empty_hospital(hospital, make_user):
    """Bay Children's: no stock at all, and one open case with a NICU bed still needed."""
    case(hospital, bed_need("nicu", quantity=1), status="open")
    return staff(make_user, hospital)


def fully_stocked(hospital):
    """Every red-cell group at or above its minimum, so no shortage at all."""
    for group, minimum in RED_CELL_MINIMUM.items():
        for _ in range(minimum):
            unit(hospital, group=group)
