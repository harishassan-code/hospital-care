"""Shared setup for the reservation tests (stories #43, #44): stock at a hospital, cases that need it, and
holds."""

import itertools
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import Role
from apps.blood.models import BloodUnit, UnitStatus
from apps.emergencies.models import EmergencyRequest, RequestItem
from apps.equipment.models import Equipment, EquipmentStatus
from apps.hospitals.models import Bed, BedStatus, Ward
from apps.matching.models import Reservation, ReservationStatus
from apps.operating_rooms.models import OperatingRoom, OrStatus

_numbers = itertools.count(1)


def staff(make_user, hospital, role=Role.NURSE):
    """A signed-in-able staff member at `hospital`, with an email nobody else in the test uses."""
    return make_user(role, email=f"{role.lower()}-{next(_numbers)}@example.com", hospital=hospital)


def unit(hospital, group="A+", component="redCells", status=UnitStatus.AVAILABLE, expires_in_days=30.0):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=f"DN-{next(_numbers):04d}",
        hospital=hospital,
        group=group,
        component=component,
        collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=expires_in_days),
        status=status,
        location="Blood fridge 1",
    )


def bed(hospital, bed_type="icu", status=BedStatus.FREE):
    ward, _ = Ward.objects.get_or_create(
        code=f"ward-{hospital.pk}", defaults={"name": "Ward", "kind": "General", "hospital": hospital}
    )
    return Bed.objects.create(ward=ward, label=f"ICU-{next(_numbers):02d}", bed_type=bed_type, status=status)


def equipment(hospital, equipment_type="ventilator", status=EquipmentStatus.AVAILABLE):
    return Equipment.objects.create(
        hospital=hospital,
        identifier=f"VENT-{next(_numbers):03d}",
        equipment_type=equipment_type,
        location="ICU bay 2",
        status=status,
    )


def room(hospital, capabilities=("cardiac",), status=OrStatus.AVAILABLE):
    return OperatingRoom.objects.create(
        hospital=hospital,
        name=f"OR {next(_numbers)}",
        capabilities=list(capabilities),
        location="Block B",
        status=status,
    )


def blood_need(group="A+", component="redCells", quantity=1, fulfilled=0):
    return {
        "resource_type": "blood",
        "blood_group": group,
        "component": component,
        "quantity": quantity,
        "fulfilled": fulfilled,
    }


def bed_need(bed_type="icu", quantity=1, fulfilled=0):
    return {"resource_type": "bed", "bed_type": bed_type, "quantity": quantity, "fulfilled": fulfilled}


def equipment_need(equipment_type="ventilator", quantity=1, fulfilled=0):
    return {
        "resource_type": "equipment",
        "equipment_type": equipment_type,
        "quantity": quantity,
        "fulfilled": fulfilled,
    }


def room_need(capability="cardiac", quantity=1, fulfilled=0):
    return {
        "resource_type": "operatingRoom",
        "capability": capability,
        "quantity": quantity,
        "fulfilled": fulfilled,
    }


def case(hospital, *needs, status="open", severity="high"):
    """A case at `hospital` with one RequestItem per need dict. Returns the case with its items."""
    reference = f"EC-2026-{next(_numbers):04d}"
    emergency = EmergencyRequest.objects.create(
        reference=reference, severity=severity, status=status, hospital=hospital
    )
    for need in needs:
        RequestItem.objects.create(request=emergency, **need)
    return emergency


def hold(item, resource, *, hospital, actor, status=ReservationStatus.HELD, expires_in_minutes=30):
    """A hold written straight to the table, for tests of the constraints and of expiry. Doesn't move the
    resource."""
    return Reservation.objects.create(
        request_item=item,
        resource=resource,
        hospital=hospital,
        reserved_by=actor,
        status=status,
        expires_at=timezone.now() + timedelta(minutes=expires_in_minutes),
    )


def status_of(obj) -> str:
    obj.refresh_from_db()
    return obj.status
