"""Story #43: a resource held for a case can only be moved by the reservation code, so a manual move from
the blood, bed, equipment or room pages can't leave a hold pointing at stock that is back on the shelf."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.blood.models import UnitStatus
from apps.equipment.models import EquipmentStatus
from apps.hospitals.models import BedStatus
from apps.matching.reservations import release, reserve
from apps.operating_rooms.models import OrStatus
from apps.resources.services import change_status
from apps.resources.state_machine import TransitionNotAllowed

from .reservation_support import (
    bed,
    bed_need,
    blood_need,
    case,
    equipment,
    equipment_need,
    room,
    room_need,
    staff,
    status_of,
    unit,
)

pytestmark = pytest.mark.django_db

KINDS = [
    (lambda h: unit(h, "A+"), blood_need("A+"), UnitStatus.RESERVED, UnitStatus.AVAILABLE),
    (lambda h: bed(h), bed_need(), BedStatus.RESERVED, BedStatus.FREE),
    (lambda h: equipment(h), equipment_need(), EquipmentStatus.RESERVED, EquipmentStatus.AVAILABLE),
    (lambda h: room(h), room_need(), OrStatus.RESERVED, OrStatus.AVAILABLE),
]


def held(here, actor, make, need):
    resource = make(here)
    emergency = case(here, need)
    [hold] = reserve(emergency.items.get(), hospital=here, quantity=1, actor=actor)
    resource.refresh_from_db()
    return resource, emergency, hold


@pytest.mark.parametrize(("make", "need", "reserved", "free"), KINDS)
def test_a_manual_move_of_a_held_resource_is_refused_and_changes_nothing(
    make_hospital, make_user, make, need, reserved, free
):
    here = make_hospital()
    nurse = staff(make_user, here)
    resource, emergency, _ = held(here, nurse, make, need)

    with pytest.raises(TransitionNotAllowed, match=emergency.reference):
        change_status(resource, "cancelReservation", actor=nurse)

    assert status_of(resource) == reserved


@pytest.mark.parametrize(("make", "need", "reserved", "free"), KINDS)
def test_once_released_the_resource_moves_freely_again(make_hospital, make_user, make, need, reserved, free):
    here = make_hospital()
    nurse = staff(make_user, here)
    resource, _, hold = held(here, nurse, make, need)
    release(hold, actor=nurse, reason="No longer needed")
    resource.refresh_from_db()

    change_status(resource, "reserve", actor=nurse)  # a manual hold with no case is still allowed

    assert status_of(resource) == reserved


def test_the_equipment_page_gets_a_409_for_held_equipment(make_hospital, make_user):
    here = make_hospital()
    nurse = staff(make_user, here)
    resource, emergency, _ = held(here, nurse, lambda h: equipment(h), equipment_need())
    client = APIClient()
    client.force_authenticate(nurse)

    res = client.post(
        reverse("equipment-action", args=[resource.pk]), {"action": "cancelReservation"}, format="json"
    )

    assert res.status_code == 409 and emergency.reference in res.json()["detail"]
    assert status_of(resource) == EquipmentStatus.RESERVED
