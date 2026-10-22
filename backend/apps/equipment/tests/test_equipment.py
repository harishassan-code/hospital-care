"""Story #26: Equipment registry."""

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.equipment.models import Equipment

pytestmark = pytest.mark.django_db

VENT = {"identifier": "vent-009", "type": "ventilator", "name": "Hamilton C6", "location": "ICU bay 4"}


def make(identifier, type_="ventilator", status="available", **extra):
    return Equipment.objects.create(
        identifier=identifier, equipment_type=type_, location="ICU", status=status, **extra
    )


def ids(response):
    return [e["identifier"] for e in response.json()]


def test_register_equipment_with_type_identifier_location_and_status(client_as):
    res = client_as(Role.NURSE).post(
        reverse("equipment-list"), {**VENT, "status": "maintenance"}, format="json"
    )
    assert res.status_code == 201
    data = res.json()
    assert data["identifier"] == "VENT-009"  # asset tags are stored upper-case
    assert (data["type"], data["location"], data["status"]) == ("ventilator", "ICU bay 4", "maintenance")
    assert AuditLog.objects.filter(action="equipment.registered").count() == 1


def test_status_defaults_to_available(client_as):
    res = client_as(Role.ADMIN).post(reverse("equipment-list"), VENT, format="json")
    assert res.json()["status"] == "available"


def test_asset_tag_must_be_unique_within_a_hospital_any_case(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    make("VENT-009", hospital=seaview)
    res = client_as(Role.NURSE, hospital=seaview).post(reverse("equipment-list"), VENT, format="json")
    assert res.status_code == 400 and "identifier" in res.json()
    # Another hospital can use the same tag.
    other = client_as(Role.NURSE, hospital=city, email="nurse2@example.com")
    assert other.post(reverse("equipment-list"), VENT, format="json").status_code == 201


@pytest.mark.parametrize(
    ("change", "field"),
    [({"type": "toaster"}, "type"), ({"location": "  "}, "location"), ({"identifier": ""}, "identifier"),
     ({"status": "broken"}, "status")],
)  # fmt: skip
def test_registration_is_validated(client_as, change, field):
    res = client_as(Role.ADMIN).post(reverse("equipment-list"), {**VENT, **change}, format="json")
    assert res.status_code == 400 and field in res.json()


def test_filter_by_type_and_status_and_search(client_as):
    make("VENT-001", status="available")
    make("VENT-002", status="maintenance")
    make("DEFIB-001", type_="defibrillator", status="available", name="Zoll R Series")
    doctor = client_as(Role.DOCTOR)
    url = reverse("equipment-list")
    assert ids(doctor.get(url, {"type": "ventilator"})) == ["VENT-001", "VENT-002"]
    assert ids(doctor.get(url, {"status": "available"})) == ["DEFIB-001", "VENT-001"]
    assert ids(doctor.get(url, {"type": "ventilator", "status": "maintenance"})) == ["VENT-002"]
    assert ids(doctor.get(url, {"q": "zoll"})) == ["DEFIB-001"]


def test_staff_only_see_their_own_hospitals_equipment(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    make("VENT-001", hospital=seaview)
    make("VENT-002", hospital=city)
    assert ids(client_as(Role.NURSE, hospital=seaview).get(reverse("equipment-list"))) == ["VENT-001"]
    assert len(client_as(Role.ADMIN).get(reverse("equipment-list")).json()) == 2  # admin without a hospital


def test_doctor_can_view_but_not_register(client_as):
    doctor = client_as(Role.DOCTOR)
    assert doctor.get(reverse("equipment-list")).status_code == 200
    assert doctor.post(reverse("equipment-list"), VENT, format="json").status_code == 403


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_roles_without_equipment_access(client_as, role):
    assert client_as(role).get(reverse("equipment-list")).status_code == 403
