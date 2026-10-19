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
