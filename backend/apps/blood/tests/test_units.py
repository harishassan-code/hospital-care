from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.blood.models import BloodUnit

pytestmark = pytest.mark.django_db


def unit(number, status, expires_in_days):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=number,
        group="B+",
        component="redCells",
        collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=expires_in_days),
        status=status,
        location="Blood fridge 1",
    )


def test_units_match_frontend_shape(client_as):
    unit("G7731 26 100000", "available", 5)
    [data] = client_as(Role.BLOOD_BANK).get(reverse("blood-units")).json()
    assert data["id"] == "G7731 26 100000"
    assert set(data) == {"id", "group", "component", "collectedAt", "expiresAt", "status", "location"}


def test_unit_past_expiry_shows_expired_unless_issued(client_as):
    unit("A", "available", -1)
    unit("B", "issued", -1)
    statuses = {u["id"]: u["status"] for u in client_as(Role.ADMIN).get(reverse("blood-units")).json()}
    assert statuses == {"A": "expired", "B": "issued"}


@pytest.mark.parametrize(("role", "code"), [(Role.DOCTOR, 200), (Role.NURSE, 403), (Role.PHARMACIST, 403)])
def test_blood_access_by_role(client_as, role, code):
    assert client_as(role).get(reverse("blood-units")).status_code == code
