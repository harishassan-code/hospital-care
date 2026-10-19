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


def payload(**overrides):
    base = {
        "id": "G7731 26 900000",
        "group": "O-",
        "component": "redCells",
        "collectedAt": timezone.now().isoformat(),
        "location": "Blood fridge 1",
    }
    return {**base, **overrides}


def test_register_unit_defaults_expiry_from_component_shelf_life(client_as):
    collected = timezone.now()
    res = client_as(Role.BLOOD_BANK).post(
        reverse("blood-units"),
        payload(component="platelets", collectedAt=collected.isoformat()),
        format="json",
    )
    assert res.status_code == 201
    unit = BloodUnit.objects.get(donation_number="G7731 26 900000")
    assert unit.status == "quarantined"
    assert unit.expires_at - unit.collected_at == timedelta(days=5)  # platelets' shelf life


def test_register_unit_rejects_duplicate_id(client_as):
    unit("G7731 26 900000", "available", 5)
    res = client_as(Role.BLOOD_BANK).post(reverse("blood-units"), payload(), format="json")
    assert res.status_code == 400
    assert "already exists" in res.json()["id"][0]


def test_register_unit_rejects_expiry_before_collection(client_as):
    collected = timezone.now()
    res = client_as(Role.BLOOD_BANK).post(
        reverse("blood-units"),
        payload(collectedAt=collected.isoformat(), expiresAt=(collected - timedelta(days=1)).isoformat()),
        format="json",
    )
    assert res.status_code == 400
    assert "expiresAt" in res.json()


@pytest.mark.parametrize(("role", "code"), [(Role.ADMIN, 201), (Role.BLOOD_BANK, 201), (Role.DOCTOR, 403)])
def test_register_unit_requires_edit_role(client_as, role, code):
    assert client_as(role).post(reverse("blood-units"), payload(), format="json").status_code == code


def test_register_unit_is_audit_logged(client_as):
    from apps.audit.models import AuditLog

    client_as(Role.BLOOD_BANK).post(reverse("blood-units"), payload(), format="json")
    entry = AuditLog.objects.get(action="bloodunit.registered")
    assert entry.target_repr == "G7731 26 900000 O- Red cells"
