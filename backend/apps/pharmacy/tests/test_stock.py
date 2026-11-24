from datetime import date

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.pharmacy.models import Batch, Medicine

pytestmark = pytest.mark.django_db


@pytest.fixture
def morphine():
    med = Medicine.objects.create(
        code="morphine",
        name="Morphine",
        strength="10 mg/mL",
        form="Injection",
        category="Opioid analgesic",
        unit="ampoules",
        reorder_level=100,
        daily_use=22,
        location="CD cabinet",
        high_alert=True,
        controlled=True,
    )
    Batch.objects.create(medicine=med, number="MOR-2403", expires_on=date(2027, 5, 1), quantity=84)
    return med


def test_stock_matches_frontend_shape(client_as, morphine):
    [data] = client_as(Role.PHARMACIST).get(reverse("pharmacy-stock")).json()
    assert data["id"] == "morphine" and data["dailyUse"] == 22.0 and data["highAlert"] is True
    assert data["batches"] == [{"number": "MOR-2403", "expiresOn": "2027-05-01", "quantity": 84}]


@pytest.mark.parametrize(("role", "code"), [(Role.NURSE, 200), (Role.BLOOD_BANK, 403), (Role.PATIENT, 403)])
def test_pharmacy_access_by_role(client_as, role, code):
    assert client_as(role).get(reverse("pharmacy-stock")).status_code == code


# #123 (B13 finding F7): stock is per hospital; the medicine list is shared.


def stock(medicine, hospital, number, month=1, quantity=10):
    expires = date(2027, month, 1)
    return Batch.objects.create(
        medicine=medicine, hospital=hospital, number=number, expires_on=expires, quantity=quantity
    )


def test_staff_see_only_their_own_hospitals_batches(client_as, make_hospital, morphine):
    home, other = make_hospital(), make_hospital(name="Seaview Hospital")
    stock(morphine, home, "HOME-1")
    stock(morphine, other, "SEA-1", month=2, quantity=20)
    [data] = client_as(Role.PHARMACIST, hospital=home).get(reverse("pharmacy-stock")).json()
    assert [b["number"] for b in data["batches"]] == ["HOME-1"]
    nurse = client_as(Role.NURSE, email="n@example.com", hospital=other)
    [data] = nurse.get(reverse("pharmacy-stock")).json()
    assert [b["number"] for b in data["batches"]] == ["SEA-1"]


def test_the_formulary_is_shared_even_where_a_hospital_holds_none(client_as, make_hospital, morphine):
    home = make_hospital()
    [data] = client_as(Role.PHARMACIST, hospital=home).get(reverse("pharmacy-stock")).json()
    assert data["id"] == "morphine" and data["batches"] == []


def test_an_admin_without_a_hospital_sees_every_hospitals_batches(client_as, make_hospital, morphine):
    home, other = make_hospital(), make_hospital(name="Seaview Hospital")
    stock(morphine, home, "HOME-1")
    stock(morphine, other, "SEA-1", month=2, quantity=20)
    [data] = client_as(Role.ADMIN).get(reverse("pharmacy-stock")).json()
    assert {b["number"] for b in data["batches"]} == {"MOR-2403", "HOME-1", "SEA-1"}


def test_the_same_lot_number_can_be_at_two_hospitals(make_hospital, morphine):
    home, other = make_hospital(), make_hospital(name="Seaview Hospital")
    for hospital in (home, other):
        stock(morphine, hospital, "LOT-9", month=3, quantity=5)
    assert Batch.objects.filter(number="LOT-9").count() == 2


def test_the_demo_seed_gives_every_hospital_its_own_stock(db):
    from django.core.management import call_command

    from apps.hospitals.models import Hospital

    call_command("seed_demo", verbosity=0)
    for hospital in Hospital.objects.all():
        # A blood bank keeps no medicines (B20); every hospital keeps its own.
        has_stock = Batch.objects.filter(hospital=hospital).exists()
        assert has_stock == (hospital.type != "bloodBank"), hospital.name
    assert not Batch.objects.filter(hospital=None).exists()
