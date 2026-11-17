"""Stories #45 and #46 in the API: allocating a hold, allocating several at once, the held list the Blood page
reads, and the allocation as a permanent record."""

from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.blood.models import UnitStatus
from apps.emergencies.models import EmergencyRequest
from apps.matching.models import Allocation, Reservation, ReservationStatus
from apps.matching.reservations import release, reserve, resource_label

from .reservation_support import bed, bed_need, blood_need, case, hold, staff, status_of, unit

pytestmark = pytest.mark.django_db

ALLOCATION_KEYS = {"id", "itemId", "resource", "hospital", "allocatedBy", "at", "note"}
HELD_KEYS = {"id", "type", "status", "case", "need", "resource", "expiresAt", "reservedBy", "canAllocate"}


@pytest.fixture
def here(make_hospital):
    return make_hospital()


@pytest.fixture
def elsewhere(make_hospital):
    return make_hospital(name="Elsewhere General")


def signed_in(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


@pytest.fixture
def bloodbank_user(make_user, here):
    return staff(make_user, here, Role.BLOOD_BANK)


@pytest.fixture
def bloodbank(bloodbank_user):
    return signed_in(bloodbank_user)


@pytest.fixture
def nurse(make_user, here):
    return signed_in(staff(make_user, here, Role.NURSE))


def allocate_url(made):
    return reverse("reservation-allocate", args=[made.pk])


def allocate_many_url():
    return reverse("reservations-allocate-many")


def held_url():
    return reverse("reservations")


def case_url(emergency):
    return reverse("emergency-case", args=[emergency.reference])


def first_item(emergency):
    return emergency.items.order_by("id").first()


def hold_for(emergency, actor, quantity=1):
    return reserve(first_item(emergency), hospital=emergency.hospital, quantity=quantity, actor=actor)


# ── Allocating one hold ──────────────────────────────────────────────────────────────────────────


def test_allocating_returns_201_and_the_case_shows_the_allocation(bloodbank, bloodbank_user, here):
    resource = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, bloodbank_user)

    response = bloodbank.post(allocate_url(made), {"note": "Handed over at triage"}, format="json")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == ALLOCATION_KEYS
    assert body["itemId"] == first_item(emergency).pk
    assert body["resource"] == resource_label(resource)
    assert body["hospital"] == {"id": here.pk, "name": here.name}
    assert body["allocatedBy"] == bloodbank_user.email
    assert body["note"] == "Handed over at triage"

    detail = bloodbank.get(case_url(emergency)).json()
    assert detail["status"] == "fulfilled"
    assert [a["id"] for a in detail["allocations"]] == [body["id"]]
    assert detail["allocations"][0]["allocatedBy"] == bloodbank_user.email
    assert detail["items"][0]["fulfilled"] == 1 and detail["items"][0]["remaining"] == 0
    assert [r["status"] for r in detail["reservations"]] == ["allocated"]
    assert status_of(resource) == UnitStatus.ISSUED


def test_allocating_the_same_hold_twice_is_409(bloodbank, bloodbank_user, here):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    (made,) = hold_for(emergency, bloodbank_user)
    assert bloodbank.post(allocate_url(made), format="json").status_code == 201

    response = bloodbank.post(allocate_url(made), format="json")

    assert response.status_code == 409
    assert "already allocated" in response.json()["detail"]


def test_a_released_hold_is_409(bloodbank, bloodbank_user, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, bloodbank_user)
    release(made, actor=bloodbank_user, reason="Not needed")

    response = bloodbank.post(allocate_url(made), format="json")

    assert response.status_code == 409


def test_an_expired_hold_is_409_and_its_unit_goes_back_to_stock(bloodbank, bloodbank_user, here):
    resource = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, bloodbank_user)
    Reservation.objects.filter(pk=made.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    response = bloodbank.post(allocate_url(made), format="json")

    assert response.status_code == 409
    assert status_of(made) == ReservationStatus.EXPIRED
    assert status_of(resource) == UnitStatus.AVAILABLE


def test_a_closed_case_is_409(bloodbank, bloodbank_user, here):
    resource = unit(here, "A+", status=UnitStatus.RESERVED)
    emergency = case(here, blood_need("A+"), status="closed")
    made = hold(first_item(emergency), resource, hospital=here, actor=bloodbank_user)

    response = bloodbank.post(allocate_url(made), format="json")

    assert response.status_code == 409
    assert status_of(resource) == UnitStatus.RESERVED


def test_a_blood_bank_user_cannot_allocate_a_bed_403(bloodbank, make_user, here):
    ward_bed = bed(here)
    emergency = case(here, bed_need())
    (made,) = hold_for(emergency, staff(make_user, here, Role.NURSE))

    response = bloodbank.post(allocate_url(made), format="json")

    assert response.status_code == 403
    assert status_of(ward_bed) == "reserved"


def test_a_nurse_allocates_a_bed_and_the_bed_is_occupied(nurse, make_user, here):
    ward_bed = bed(here)
    emergency = case(here, bed_need())
    (made,) = hold_for(emergency, staff(make_user, here, Role.NURSE))

    response = nurse.post(allocate_url(made), format="json")

    assert response.status_code == 201
    assert status_of(ward_bed) == "occupied"


def test_another_hospitals_hold_is_404_for_a_non_admin(bloodbank, make_user, here, elsewhere):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, staff(make_user, here, Role.BLOOD_BANK))
    elsewhere_bank = signed_in(staff(make_user, elsewhere, Role.BLOOD_BANK))

    response = elsewhere_bank.post(allocate_url(made), format="json")

    assert response.status_code == 404
    assert bloodbank.post(allocate_url(made), format="json").status_code == 201


def test_an_admin_allocates_a_hold_at_any_hospital(make_user, here, elsewhere):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, staff(make_user, here, Role.BLOOD_BANK))
    admin = signed_in(make_user(Role.ADMIN))

    response = admin.post(allocate_url(made), format="json")

    assert response.status_code == 201


def test_the_allocation_cannot_be_changed_or_deleted_through_the_api(bloodbank, bloodbank_user, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, bloodbank_user)
    allocation = bloodbank.post(allocate_url(made), format="json").json()

    assert bloodbank.put(allocate_url(made), {}, format="json").status_code == 405
    assert bloodbank.patch(allocate_url(made), {}, format="json").status_code == 405
    assert bloodbank.delete(allocate_url(made)).status_code == 405
    assert bloodbank.patch(f"/api/reservations/allocations/{allocation['id']}/", {}).status_code == 404
    assert bloodbank.delete(f"/api/reservations/allocations/{allocation['id']}/").status_code == 404
    assert Allocation.objects.get().note == ""


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
def test_the_admin_site_shows_allocations_read_only(make_user, here, bloodbank_user):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, bloodbank_user)
    allocation = signed_in(bloodbank_user).post(allocate_url(made), format="json").json()
    superuser = make_user(Role.ADMIN, is_superuser=True, is_staff=True)
    site = APIClient()
    site.force_login(superuser)

    assert site.get("/admin/matching/allocation/").status_code == 200
    assert site.get("/admin/matching/allocation/add/").status_code == 403
    assert site.get(f"/admin/matching/allocation/{allocation['id']}/delete/").status_code == 403
    assert (
        site.post(f"/admin/matching/allocation/{allocation['id']}/change/", {"note": "x"}).status_code == 403
    )
    assert Allocation.objects.get().note == ""


# ── Held reservations: the Blood page's list ─────────────────────────────────────────────────────


def test_the_held_list_is_scoped_to_the_users_hospital_and_role(make_user, here, elsewhere):
    blood_here = case(here, blood_need("A+"))
    blood_there = case(elsewhere, blood_need("A+"))
    bed_here = case(here, bed_need())
    bank = staff(make_user, here, Role.BLOOD_BANK)
    hold(first_item(blood_here), unit(here, "A+", status=UnitStatus.RESERVED), hospital=here, actor=bank)
    hold(
        first_item(blood_there),
        unit(elsewhere, "A+", status=UnitStatus.RESERVED),
        hospital=elsewhere,
        actor=bank,
    )
    hold(first_item(bed_here), bed(here, status="reserved"), hospital=here, actor=bank)
    admin = signed_in(make_user(Role.ADMIN))

    mine = signed_in(bank).get(held_url(), {"type": "blood"}).json()
    assert [entry["case"]["reference"] for entry in mine] == [blood_here.reference]
    assert set(mine[0]) == HELD_KEYS

    everything = admin.get(held_url(), {"type": "blood"}).json()
    assert sorted(entry["case"]["reference"] for entry in everything) == sorted(
        [blood_here.reference, blood_there.reference]
    )

    nurse_list = signed_in(staff(make_user, here, Role.NURSE)).get(held_url()).json()
    assert [entry["type"] for entry in nurse_list] == ["bed"]
    assert signed_in(staff(make_user, here, Role.NURSE)).get(held_url(), {"type": "blood"}).status_code == 403
    assert signed_in(make_user(Role.PATIENT)).get(held_url()).status_code == 403


def test_the_held_list_is_most_urgent_first_then_by_expiry(make_user, here):
    bank = staff(make_user, here, Role.BLOOD_BANK)
    high_older = case(here, blood_need("A+", quantity=2), severity="high")
    critical = case(here, blood_need("A+"), severity="critical")
    high_newer = case(here, blood_need("A+"), severity="high")
    EmergencyRequest.objects.filter(pk=high_older.pk).update(created_at=timezone.now() - timedelta(hours=3))
    EmergencyRequest.objects.filter(pk=high_newer.pk).update(created_at=timezone.now() - timedelta(hours=1))
    later, sooner = (
        hold(
            first_item(high_older),
            unit(here, "A+", status=UnitStatus.RESERVED),
            hospital=here,
            actor=bank,
            expires_in_minutes=30,
        ),
        hold(
            first_item(high_older),
            unit(here, "A+", status=UnitStatus.RESERVED),
            hospital=here,
            actor=bank,
            expires_in_minutes=10,
        ),
    )
    crit = hold(
        first_item(critical),
        unit(here, "A+", status=UnitStatus.RESERVED),
        hospital=here,
        actor=bank,
        expires_in_minutes=120,
    )
    newer = hold(
        first_item(high_newer),
        unit(here, "A+", status=UnitStatus.RESERVED),
        hospital=here,
        actor=bank,
        expires_in_minutes=5,
    )

    listed = signed_in(bank).get(held_url(), {"type": "blood"}).json()

    assert [entry["id"] for entry in listed] == [crit.pk, sooner.pk, later.pk, newer.pk]


def test_the_held_list_shows_what_is_remaining_and_who_may_allocate(make_user, here):
    bank_user = staff(make_user, here, Role.BLOOD_BANK)
    emergency = case(here, blood_need("A+", quantity=3))
    unit(here, "A+")
    (made,) = hold_for(emergency, bank_user)
    doctor = signed_in(staff(make_user, here, Role.DOCTOR))

    own = signed_in(bank_user).get(held_url(), {"type": "blood"}).json()[0]
    viewer = doctor.get(held_url(), {"type": "blood"}).json()[0]

    assert own["need"] == {
        "itemId": first_item(emergency).pk,
        "label": "A+ red cells",
        "quantity": 3,
        "fulfilled": 0,
        "remaining": 3,
    }
    assert own["case"] == {"reference": emergency.reference, "severity": "high", "status": "matching"}
    assert own["id"] == made.pk and own["canAllocate"] is True
    assert viewer["canAllocate"] is False


# ── Allocating several at once ───────────────────────────────────────────────────────────────────


def test_allocate_many_allocates_all_in_the_order_asked(bloodbank, bloodbank_user, here):
    for _ in range(2):
        unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    holds = hold_for(emergency, bloodbank_user, quantity=2)

    response = bloodbank.post(allocate_many_url(), {"ids": [holds[1].pk, holds[0].pk]}, format="json")

    assert response.status_code == 201
    assert [a["id"] for a in response.json()] == [
        Allocation.objects.get(reservation=holds[1]).pk,
        Allocation.objects.get(reservation=holds[0]).pk,
    ]
    assert case_detail_status(emergency) == "fulfilled"


def test_allocate_many_is_all_or_nothing_over_the_api(bloodbank, bloodbank_user, here):
    resource = unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    holds = hold_for(emergency, bloodbank_user, quantity=2)
    Reservation.objects.filter(pk=holds[1].pk).update(
        status=ReservationStatus.RELEASED, ended_at=timezone.now()
    )

    response = bloodbank.post(allocate_many_url(), {"ids": [holds[0].pk, holds[1].pk]}, format="json")

    assert response.status_code == 409
    assert status_of(resource) == UnitStatus.RESERVED
    assert status_of(holds[0]) == ReservationStatus.HELD
    assert not Allocation.objects.exists()


def test_allocate_many_refuses_another_hospitals_hold_with_404(make_user, here, elsewhere):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, staff(make_user, here, Role.BLOOD_BANK))
    elsewhere_bank = signed_in(staff(make_user, elsewhere, Role.BLOOD_BANK))

    response = elsewhere_bank.post(allocate_many_url(), {"ids": [made.pk]}, format="json")

    assert response.status_code == 404
    assert not Allocation.objects.exists()


def test_allocate_many_rejects_a_repeated_id_and_an_empty_list(bloodbank, bloodbank_user, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = hold_for(emergency, bloodbank_user)

    assert bloodbank.post(allocate_many_url(), {"ids": [made.pk, made.pk]}, format="json").status_code == 400
    assert bloodbank.post(allocate_many_url(), {"ids": []}, format="json").status_code == 400
    assert not Allocation.objects.exists()


def case_detail_status(emergency) -> str:
    emergency.refresh_from_db()
    return emergency.status
