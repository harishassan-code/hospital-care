"""B13 F1 and F2: a donor registered at one hospital can't be booked for a donation, or linked to a blood
unit, by another hospital. An unknown donor code gets the same 404, so the reply shows neither the donor
nor the donation history that the interval rule would reveal. Admins, who see everything, can do both."""

from datetime import timedelta

import pytest
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.blood import services
from apps.blood.models import BloodUnit, DonationAppointment, Donor
from apps.blood.serializers import BloodUnitCreateSerializer

pytestmark = pytest.mark.django_db

OTHER_CODE = "DNR-00009"  # registered at the other hospital
UNKNOWN_CODE = "DNR-99999"


@pytest.fixture
def hospitals(make_hospital):
    return make_hospital("Here Hospital"), make_hospital("There Hospital")


def donor_at(hospital, code=OTHER_CODE, group="O-", name="Asha Other"):
    return Donor.objects.create(code=code, full_name=name, blood_group=group, hospital=hospital)


def give(donor, hospital, days_ago):
    """A unit from an earlier donation, so a new one from this donor breaks the minimum interval."""
    when = timezone.now() - timedelta(days=days_ago)
    return BloodUnit.objects.create(
        donation_number="OLD-1",
        group=donor.blood_group,
        component="redCells",
        collected_at=when,
        expires_at=when + timedelta(days=42),
        location="Blood fridge",
        donor=donor,
        hospital=hospital,
    )


def next_slot(days=2):
    return (timezone.localtime() + timedelta(days=days)).replace(hour=10, minute=0, second=0, microsecond=0)


def book(client, donor_id, starts_at=None):
    body = {"donorId": donor_id, "startsAt": (starts_at or next_slot()).isoformat()}
    return client.post(reverse("blood-appointments"), body, format="json")


def unit_body(number, donor_id, group="O-"):
    return {
        "id": number,
        "group": group,
        "component": "plasma",
        "collectedAt": timezone.now().isoformat(),
        "location": "Plasma freezer A",
        "donorId": donor_id,
    }


def register_unit(client, number, donor_id, group="O-"):
    return client.post(reverse("blood-units"), unit_body(number, donor_id, group), format="json")


# ── F1: appointments ────────────────────────────────────────────────────────────────────────────


def test_blood_bank_cannot_book_a_donor_from_another_hospital(client_as, hospitals):
    here, there = hospitals
    donor_at(there)
    res = book(client_as(Role.BLOOD_BANK, hospital=here), OTHER_CODE)
    assert res.status_code == 404
    assert "Asha Other" not in res.content.decode()
    assert not DonationAppointment.objects.exists()


def test_another_hospitals_donor_gets_the_same_reply_as_an_unknown_code(client_as, hospitals):
    here, there = hospitals
    donor_at(there)
    staff = client_as(Role.BLOOD_BANK, hospital=here)
    other, unknown = book(staff, OTHER_CODE), book(staff, UNKNOWN_CODE)
    assert (other.status_code, other.json()) == (unknown.status_code, unknown.json())


def test_a_donor_at_the_users_own_hospital_can_be_booked(client_as, hospitals):
    here, _ = hospitals
    donor_at(here)
    assert book(client_as(Role.BLOOD_BANK, hospital=here), OTHER_CODE).status_code == 201


def test_admins_can_book_a_donor_from_any_hospital(client_as, hospitals):
    _, there = hospitals
    donor_at(there)
    assert book(client_as(Role.ADMIN), OTHER_CODE).status_code == 201


def test_the_service_refuses_a_donor_outside_the_actors_hospital(make_user, hospitals):
    """The service checks again, so a caller that skips the view's lookup still can't book across them."""
    here, there = hospitals
    donor = donor_at(there)
    with pytest.raises(Http404):
        services.book_appointment(donor, next_slot(), actor=make_user(Role.BLOOD_BANK, hospital=here))
    assert not DonationAppointment.objects.exists()


# ── F2: blood units ─────────────────────────────────────────────────────────────────────────────


def test_blood_bank_cannot_link_a_unit_to_another_hospitals_donor(client_as, hospitals):
    here, there = hospitals
    give(donor_at(there), there, days_ago=20)  # a recent donation there would trip the interval rule
    res = register_unit(client_as(Role.BLOOD_BANK, hospital=here), "U9", OTHER_CODE)
    assert res.status_code == 404
    assert "less than" not in res.content.decode()  # the interval message would reveal the donation
    assert not BloodUnit.objects.filter(donation_number="U9").exists()


def test_linking_to_another_hospitals_donor_gets_the_same_reply_as_an_unknown_code(client_as, hospitals):
    here, there = hospitals
    donor_at(there)
    staff = client_as(Role.BLOOD_BANK, hospital=here)
    other, unknown = register_unit(staff, "U9", OTHER_CODE), register_unit(staff, "U10", UNKNOWN_CODE)
    assert (other.status_code, other.json()) == (unknown.status_code, unknown.json())


def test_a_donor_at_the_users_own_hospital_can_be_linked(client_as, hospitals):
    here, _ = hospitals
    donor_at(here)
    assert register_unit(client_as(Role.BLOOD_BANK, hospital=here), "U9", OTHER_CODE).status_code == 201


def test_admins_can_link_a_unit_to_a_donor_from_any_hospital(client_as, hospitals):
    _, there = hospitals
    donor_at(there)
    assert register_unit(client_as(Role.ADMIN), "U9", OTHER_CODE).status_code == 201


def test_the_service_refuses_a_unit_linked_to_another_hospitals_donor(make_user, hospitals):
    """A serializer built for an admin accepts any donor; the service still refuses blood bank staff."""
    here, there = hospitals
    donor_at(there)
    serializer = BloodUnitCreateSerializer(
        data=unit_body("U9", OTHER_CODE), context={"user": make_user(Role.ADMIN)}
    )
    assert serializer.is_valid(), serializer.errors
    with pytest.raises(Http404):
        services.register_unit(serializer, make_user(Role.BLOOD_BANK, hospital=here, email="bb@here.example"))
    assert not BloodUnit.objects.filter(donation_number="U9").exists()
