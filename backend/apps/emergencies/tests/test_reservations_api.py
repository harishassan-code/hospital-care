"""Story #43 in the API: reserving a case's own stock, releasing a hold, and the holds on the case detail."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.blood.models import UnitStatus
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.tests.reservation_support import (
    bed,
    bed_need,
    blood_need,
    case,
    equipment,
    equipment_need,
    hold,
    room,
    room_need,
    staff,
    status_of,
    unit,
)

pytestmark = pytest.mark.django_db

HOLD_KEYS = {
    "id",
    "itemId",
    "resource",
    "hospital",
    "status",
    "expiresAt",
    "reservedBy",
    "canAllocate",
    "transfer",  # story #47: the live transfer the hold is pinned to, or null
}


@pytest.fixture
def here(make_hospital):
    return make_hospital()


@pytest.fixture
def doctor(client_as, here):
    return client_as(Role.DOCTOR, hospital=here)


def reservations_url(emergency):
    return reverse("emergency-case-reservations", args=[emergency.reference])


def release_url(emergency, hold_id):
    return reverse("emergency-case-reservation-release", args=[emergency.reference, hold_id])


def detail(client, emergency):
    return client.get(reverse("emergency-case", args=[emergency.reference])).json()


def reserve_body(emergency, quantity, index=0):
    return {"itemId": emergency.items.order_by("id")[index].pk, "quantity": quantity}


def reserve_via_api(client, emergency, quantity, index=0):
    return client.post(reservations_url(emergency), reserve_body(emergency, quantity, index), format="json")


def expire(made):
    """Make a hold's time run out a minute ago, as if the clock had moved on."""
    Reservation.objects.filter(pk=made.pk).update(expires_at=timezone.now() - timedelta(minutes=1))


# ── Reserving ──────────────────────────────────────────────────────────────────────────────────


def test_reserving_returns_201_with_the_holds_and_the_case_shows_them(doctor, here):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))

    response = reserve_via_api(doctor, emergency, 2)

    assert response.status_code == 201
    holds = response.json()
    assert len(holds) == 2
    for shown in holds:
        assert set(shown) == HOLD_KEYS
        assert shown["resource"].startswith("A+ red cells DN-")
        assert shown["hospital"] == {"id": here.pk, "name": here.name}
        assert shown["status"] == "held"
        assert shown["itemId"] == emergency.items.get().pk
        assert shown["reservedBy"] == "doctor@example.com"

    case_json = detail(doctor, emergency)
    assert [shown["id"] for shown in case_json["reservations"]] == [shown["id"] for shown in holds]
    [need] = case_json["items"]
    assert (need["reserved"], need["localAvailable"], need["shortfall"]) == (2, 0, 0)
    assert case_json["shortfallTotal"] == 0
    assert case_json["status"] == "matching"


@pytest.mark.parametrize(
    ("make", "need", "prefix"),
    [
        (lambda h: bed(h, "icu"), bed_need("icu"), "Bed ICU-"),
        (lambda h: equipment(h, "ventilator"), equipment_need("ventilator"), "Ventilator VENT-"),
        (lambda h: room(h), room_need(), "OR "),
    ],
)
def test_each_resource_is_named_the_way_staff_name_it(doctor, here, make, need, prefix):
    make(here)
    emergency = case(here, need)

    [shown] = reserve_via_api(doctor, emergency, 1).json()

    assert shown["resource"].startswith(prefix)


def test_partial_stock_takes_what_there_is_and_returns_only_those(doctor, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=3))

    response = reserve_via_api(doctor, emergency, 3)

    assert response.status_code == 201
    assert len(response.json()) == 1


def test_nothing_free_is_400_with_the_reason_and_changes_nothing(doctor, here):
    stock = unit(here, "A+", status=UnitStatus.RESERVED)
    emergency = case(here, blood_need("A+"))

    response = reserve_via_api(doctor, emergency, 1)

    assert response.status_code == 400
    assert response.json() == {"detail": "No matching stock is free at this hospital."}
    assert status_of(stock) == UnitStatus.RESERVED


def test_asking_for_more_than_the_need_has_left_is_400(doctor, here):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=1))

    response = reserve_via_api(doctor, emergency, 2)

    assert response.status_code == 400
    assert response.json() == {"detail": "Only 1 more can be reserved for this need."}


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"itemId": "not-a-number", "quantity": 1}, "itemId"),
        ({"quantity": 1}, "itemId"),
        ({"itemId": 1, "quantity": 0}, "quantity"),
    ],
)
def test_a_malformed_request_is_400_naming_the_field(doctor, here, body, field):
    emergency = case(here, blood_need("A+"))

    response = doctor.post(reservations_url(emergency), body, format="json")

    assert response.status_code == 400
    assert field in response.json()


def test_a_need_from_another_case_is_400(doctor, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    other = case(here, blood_need("A+"))

    response = doctor.post(
        reservations_url(emergency), {"itemId": other.items.get().pk, "quantity": 1}, format="json"
    )

    assert response.status_code == 400
    assert "itemId" in response.json()


def test_a_closed_case_cannot_reserve(doctor, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"), status="closed")

    response = reserve_via_api(doctor, emergency, 1)

    assert response.status_code == 400
    assert response.json() == {"detail": "Can't reserve stock for a case that is closed."}


# ── Who may do it ──────────────────────────────────────────────────────────────────────────────


def test_another_hospitals_case_is_404_for_reserving_and_releasing(client_as, make_hospital, here):
    there = make_hospital(name="Elsewhere")
    emergency = case(there, blood_need("A+"))
    stock = unit(there, "A+")
    owner = client_as(Role.DOCTOR, hospital=there)
    [made] = reserve_via_api(owner, emergency, 1).json()
    outsider = client_as(Role.NURSE, hospital=here)  # a nurse at another hospital, with edit rights

    assert reserve_via_api(outsider, emergency, 1).status_code == 404
    assert outsider.post(release_url(emergency, made["id"])).status_code == 404
    assert status_of(stock) == UnitStatus.RESERVED


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_a_role_without_edit_on_emergencies_is_403_and_holds_nothing(client_as, here, role):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))

    response = reserve_via_api(client_as(role, hospital=here), emergency, 1)

    assert response.status_code == 403
    assert not Reservation.objects.exists()


def test_a_nurse_at_the_hospital_can_reserve_and_release(client_as, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    nurse = client_as(Role.NURSE, hospital=here)
    [made] = reserve_via_api(nurse, emergency, 1).json()

    assert nurse.post(release_url(emergency, made["id"])).status_code == 200


# ── Releasing ──────────────────────────────────────────────────────────────────────────────────


def test_releasing_returns_the_hold_and_frees_the_stock(doctor, here):
    stock = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    [made] = reserve_via_api(doctor, emergency, 1).json()

    response = doctor.post(release_url(emergency, made["id"]))

    assert response.status_code == 200
    assert response.json()["status"] == "released"
    assert status_of(stock) == UnitStatus.AVAILABLE
    assert detail(doctor, emergency)["reservations"] == []


def test_releasing_a_hold_that_is_no_longer_held_is_409(doctor, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    [made] = reserve_via_api(doctor, emergency, 1).json()
    doctor.post(release_url(emergency, made["id"]))

    response = doctor.post(release_url(emergency, made["id"]))

    assert response.status_code == 409
    assert response.json() == {"detail": "This reservation is released, so it can't be released."}


def test_releasing_a_hold_whose_time_has_run_out_is_409_and_frees_the_stock(doctor, here, make_user):
    stock = unit(here, "A+", status=UnitStatus.RESERVED)
    emergency = case(here, blood_need("A+"))
    made = hold(emergency.items.get(), stock, hospital=here, actor=staff(make_user, here))
    expire(made)

    response = doctor.post(release_url(emergency, made.pk))

    assert response.status_code == 409
    assert status_of(stock) == UnitStatus.AVAILABLE


# ── Expired holds are freed before anyone looks ───────────────────────────────────────────────


def test_the_candidates_and_the_case_detail_free_expired_holds_before_answering(doctor, here):
    stock = unit(here, "A+")
    holder = case(here, blood_need("A+"))
    [made] = reserve_via_api(doctor, holder, 1).json()
    expire(Reservation.objects.get(pk=made["id"]))
    asking = case(here, blood_need("A+"))

    assert doctor.get(reverse("emergency-case-candidates", args=[asking.reference])).status_code == 200

    assert status_of(stock) == UnitStatus.AVAILABLE
    assert detail(doctor, holder)["reservations"] == []


def test_reserving_frees_expired_holds_first_so_their_stock_can_be_taken(doctor, here):
    stock = unit(here, "A+")
    holder = case(here, blood_need("A+"))
    [made] = reserve_via_api(doctor, holder, 1).json()
    expire(Reservation.objects.get(pk=made["id"]))
    other = case(here, blood_need("A+"))

    response = reserve_via_api(doctor, other, 1)

    assert response.status_code == 201
    assert status_of(stock) == UnitStatus.RESERVED
    assert Reservation.objects.get(pk=made["id"]).status == ReservationStatus.EXPIRED


# ── The detail's shape ─────────────────────────────────────────────────────────────────────────


def test_the_detail_lists_held_and_allocated_holds_and_counts_only_held_per_need(doctor, here, make_user):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=3))
    reserve_via_api(doctor, emergency, 1)
    allocated_stock = unit(here, "A+", status=UnitStatus.RESERVED)
    hold(
        emergency.items.get(),
        allocated_stock,
        hospital=here,
        actor=staff(make_user, here),
        status=ReservationStatus.ALLOCATED,
    )
    released_stock = unit(here, "A+")
    hold(
        emergency.items.get(),
        released_stock,
        hospital=here,
        actor=staff(make_user, here),
        status=ReservationStatus.RELEASED,
    )

    case_json = detail(doctor, emergency)

    assert sorted(shown["status"] for shown in case_json["reservations"]) == ["allocated", "held"]
    [need] = case_json["items"]
    assert need["reserved"] == 1


def test_the_detail_of_a_case_with_no_holds_has_an_empty_list(doctor, here):
    emergency = case(here, blood_need("A+"))

    case_json = detail(doctor, emergency)

    assert case_json["reservations"] == []
    assert case_json["items"][0]["reserved"] == 0


@pytest.mark.parametrize(
    ("make", "need"),
    [
        (lambda h: bed(h, "icu"), bed_need("icu")),
        (lambda h: equipment(h, "ventilator"), equipment_need("ventilator")),
        (lambda h: room(h), room_need()),
    ],
)
def test_a_held_resource_of_each_other_type_shows_on_the_detail(doctor, here, make, need):
    make(here)
    emergency = case(here, need)
    reserve_via_api(doctor, emergency, 1)

    [shown] = detail(doctor, emergency)["reservations"]

    assert shown["status"] == "held"
    assert shown["resource"]


def test_the_detail_query_count_does_not_grow_with_the_holds(doctor, here, django_assert_max_num_queries):
    def count(emergency):
        with CaptureQueriesContext(connection) as context:
            assert doctor.get(reverse("emergency-case", args=[emergency.reference])).status_code == 200
        return len(context.captured_queries)

    small = case(here, blood_need("A+"))
    unit(here, "A+")
    reserve_via_api(doctor, small, 1)
    few = count(small)

    big = case(here, blood_need("A+", quantity=5), blood_need("A+", quantity=5), blood_need("O-", quantity=1))
    for _ in range(5):
        unit(here, "A+")
    unit(here, "O-")
    assert reserve_via_api(doctor, big, 5, index=0).status_code == 201
    with django_assert_max_num_queries(20):
        many = count(big)

    assert many == few
