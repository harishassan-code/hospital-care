"""Stories #45 and #46 on the case: its allocations, what is left of each need, who may allocate."""

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.matching.allocations import allocate
from apps.matching.reservations import reserve
from apps.matching.tests.reservation_support import blood_need, case, staff, unit

pytestmark = pytest.mark.django_db


@pytest.fixture
def here(make_hospital):
    return make_hospital()


def detail(client, emergency):
    return client.get(reverse("emergency-case", args=[emergency.reference])).json()


def test_the_case_lists_its_allocations_and_what_remains_of_each_need(make_user, here, client_as):
    bank = staff(make_user, here, Role.BLOOD_BANK)
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=3))
    item = emergency.items.get()
    holds = reserve(item, hospital=here, quantity=2, actor=bank)
    allocate(holds[0].pk, actor=bank, note="First unit")

    body = detail(client_as(Role.BLOOD_BANK, hospital=here), emergency)

    assert [a["note"] for a in body["allocations"]] == ["First unit"]
    allocation = body["allocations"][0]
    assert allocation["itemId"] == item.pk
    assert allocation["hospital"] == {"id": here.pk, "name": here.name}
    assert allocation["allocatedBy"] == bank.email
    assert body["items"][0]["quantity"] == 3
    assert body["items"][0]["fulfilled"] == 1
    assert body["items"][0]["remaining"] == 2
    assert body["items"][0]["reserved"] == 1


def test_an_allocated_unit_is_counted_once_in_the_shortfall(make_user, here, client_as):
    """The need wants two units and there is one. After the held unit is allocated, one is still short: the
    allocated unit is in `fulfilled`, not counted again as a hold."""
    bank = staff(make_user, here, Role.BLOOD_BANK)
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    (made,) = reserve(emergency.items.get(), hospital=here, quantity=1, actor=bank)
    allocate(made.pk, actor=bank)

    body = detail(client_as(Role.BLOOD_BANK, hospital=here), emergency)

    assert body["items"][0]["remaining"] == 1
    assert body["items"][0]["localAvailable"] == 0
    assert body["items"][0]["shortfall"] == 1
    assert body["shortfallTotal"] == 1


def test_a_held_reservation_says_who_may_allocate_it(make_user, here, client_as):
    bank = staff(make_user, here, Role.BLOOD_BANK)
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    first, second = reserve(emergency.items.get(), hospital=here, quantity=2, actor=bank)
    allocate(first.pk, actor=bank)

    as_bank = detail(client_as(Role.BLOOD_BANK, hospital=here), emergency)
    as_doctor = detail(client_as(Role.DOCTOR, hospital=here), emergency)

    by_status = {r["status"]: r for r in as_bank["reservations"]}
    assert by_status["allocated"]["canAllocate"] is False
    assert by_status["held"]["id"] == second.pk and by_status["held"]["canAllocate"] is True
    assert all(r["canAllocate"] is False for r in as_doctor["reservations"])
