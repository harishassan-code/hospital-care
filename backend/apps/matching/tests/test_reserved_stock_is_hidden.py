"""Story #43: a reserved resource disappears from every search, with no filter added for it. Each search keeps
to its available or free status, so a hold hides a resource. These tests prove that for each search and
each type."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.blood.models import BloodUnit
from apps.blood.services import usable_units
from apps.emergencies.availability import local_availability, shortfall_items
from apps.equipment.models import Equipment
from apps.hospitals.models import Bed, BedStatus
from apps.matching.candidates import REGISTRY, candidates_for_case, find_candidates
from apps.matching.compatibility import compatible_units
from apps.matching.reservations import release, release_expired, reserve
from apps.operating_rooms.models import OperatingRoom
from apps.resources.services import change_status

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
    unit,
)

pytestmark = pytest.mark.django_db

# Each type: how to stock a hospital, and the need a case has for it.
KINDS = {
    "blood": (lambda h: unit(h, "A+"), lambda: blood_need("A+")),
    "bed": (lambda h: bed(h), lambda: bed_need()),
    "equipment": (lambda h: equipment(h), lambda: equipment_need()),
    "room": (lambda h: room(h), lambda: room_need()),
}


@pytest.fixture
def here(make_hospital):
    return make_hospital(name="Here")


@pytest.fixture
def there(make_hospital):
    return make_hospital(name="There")


@pytest.fixture
def nurse(make_user, here):
    return staff(make_user, here)


def hold_at(hospital, actor, need):
    """Stock the need at `hospital` is held for another case there. Returns the case that holds it."""
    holder = case(hospital, need)
    reserve(holder.items.get(), hospital=hospital, quantity=1, actor=actor)
    return holder


@pytest.mark.parametrize("kind", KINDS)
def test_a_held_resource_is_not_counted_as_local_availability(here, nurse, kind):
    make, need = KINDS[kind]
    make(here)
    hold_at(here, nurse, need())
    asking = case(here, need())

    [row] = local_availability(asking)

    assert row.available == 0
    assert row.shortfall == 1


@pytest.mark.parametrize("kind", KINDS)
def test_a_held_resource_is_not_a_candidate_for_another_case(here, there, nurse, kind):
    make, need = KINDS[kind]
    make(there)
    hold_at(there, nurse, need())
    asking = case(here, need())

    found = find_candidates(asking.items.get(), origin_hospital=here, needed=1)

    assert [c.hospital.pk for c in found] == []


@pytest.mark.parametrize("kind", KINDS)
def test_a_held_resource_is_not_in_the_registry_search_for_a_need(here, nurse, kind):
    make, need = KINDS[kind]
    make(here)
    hold_at(here, nurse, need())
    item = case(here, need()).items.get()

    assert not REGISTRY[item.resource_type](item).exists()


def test_a_held_blood_unit_is_not_a_compatible_unit(here, nurse):
    unit(here, "A+")
    hold_at(here, nurse, blood_need("A+"))

    assert not compatible_units("A+", "redCells").exists()
    assert not usable_units(BloodUnit.objects.all()).exists()


def test_a_held_bed_is_not_free(here, nurse):
    bed(here, "icu")
    hold_at(here, nurse, {"resource_type": "bed", "bed_type": "icu", "quantity": 1, "fulfilled": 0})

    assert not Bed.objects.filter(status=BedStatus.FREE).exists()


def test_a_held_piece_of_equipment_is_not_matchable(here, nurse):
    equipment(here)
    hold_at(here, nurse, equipment_need())

    assert not Equipment.objects.matchable().exists()


def test_a_held_operating_room_is_not_matchable(here, nurse):
    room(here)
    hold_at(here, nurse, room_need())

    assert not OperatingRoom.objects.matchable().exists()


@pytest.mark.parametrize("kind", KINDS)
def test_the_stock_comes_back_when_the_hold_is_released(here, nurse, kind):
    make, need = KINDS[kind]
    make(here)
    holder = case(here, need())
    [made] = reserve(holder.items.get(), hospital=here, quantity=1, actor=nurse)
    asking = case(here, need())
    assert [row.available for row in local_availability(asking)] == [0]

    release(made, actor=nurse, reason="Released by staff")

    assert [row.available for row in local_availability(asking)] == [1]
    assert REGISTRY[asking.items.get().resource_type](asking.items.get()).exists()


def test_the_stock_comes_back_when_the_hold_expires(here, nurse):
    make, need = KINDS["bed"]
    make(here)
    holder = case(here, need())
    reserve(holder.items.get(), hospital=here, quantity=1, actor=nurse)
    asking = case(here, need())

    release_expired(now=timezone.now() + timedelta(hours=1))

    assert [row.available for row in local_availability(asking)] == [1]


def test_a_case_does_not_ask_other_hospitals_for_what_it_holds_here(here, nurse):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    reserve(emergency.items.get(), hospital=here, quantity=2, actor=nurse)

    [row] = local_availability(emergency)

    assert (row.held, row.available, row.shortfall) == (2, 0, 0)
    assert shortfall_items(emergency) == []
    assert candidates_for_case(emergency) == []


def test_a_need_partly_held_here_asks_only_for_the_rest(here, there, nurse):
    unit(here, "A+")
    unit(there, "A+")
    unit(there, "A+")
    emergency = case(here, blood_need("A+", quantity=3))
    reserve(emergency.items.get(), hospital=here, quantity=1, actor=nurse)

    [(item, shortfall)] = shortfall_items(emergency)

    assert shortfall == 2
    assert item.request_id == emergency.pk


def test_a_held_unit_that_is_issued_is_not_offered_again(here, nurse):
    stock = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    reserve(emergency.items.get(), hospital=here, quantity=1, actor=nurse)
    # As allocation (#45) would: only reservation code may move a held unit.
    change_status(stock, "issue", actor=nurse, reason="Given to the patient", held_ok=True)

    assert not compatible_units("A+", "redCells").exists()
    assert not REGISTRY["blood"](emergency.items.get()).exists()
