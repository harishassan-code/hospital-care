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


# Story #27: operational status.


def act(client, pk, action, **extra):
    return client.post(reverse("equipment-action", args=[pk]), {"action": action, **extra}, format="json")


@pytest.mark.parametrize(
    ("start", "action", "end"),
    [
        ("available", "use", "inUse"),
        ("inUse", "release", "available"),
        ("available", "startMaintenance", "maintenance"),
        ("inUse", "startMaintenance", "maintenance"),
        ("maintenance", "finishMaintenance", "available"),
        ("available", "outOfService", "outOfService"),
        ("maintenance", "outOfService", "outOfService"),
        ("outOfService", "returnToService", "maintenance"),
        # Story #43: a hold on equipment, and its release or use.
        ("available", "reserve", "reserved"),
        ("reserved", "cancelReservation", "available"),
        ("reserved", "use", "inUse"),
    ],
)
def test_allowed_moves(client_as, start, action, end):
    item = make("VENT-001", status=start)
    res = act(client_as(Role.NURSE), item.pk, action)
    assert res.status_code == 200 and res.json()["status"] == end


def test_status_change_is_saved_and_audit_logged(client_as):
    item = make("VENT-001")
    res = act(client_as(Role.NURSE), item.pk, "use", reason="Patient moved to bay 2")
    assert res.status_code == 200 and res.json()["statusSince"]
    item.refresh_from_db()
    assert item.status == "inUse"
    entry = AuditLog.objects.get(action="equipment.status_changed")
    assert entry.actor_email == "nurse@example.com" and entry.target_repr == "VENT-001 (Ventilator)"
    assert (entry.before, entry.after, entry.reason) == (
        {"status": "available"},
        {"status": "inUse"},
        "Patient moved to bay 2",
    )


def test_refused_move_is_409_and_changes_nothing(client_as):
    item = make("VENT-001", status="maintenance")
    res = act(client_as(Role.NURSE), item.pk, "use")
    assert res.status_code == 409 and "piece of equipment" in res.json()["detail"]
    item.refresh_from_db()
    assert item.status == "maintenance"
    assert not AuditLog.objects.filter(action="equipment.status_changed").exists()


def test_unknown_action_is_400(client_as):
    item = make("VENT-001")
    assert act(client_as(Role.NURSE), item.pk, "teleport").status_code == 400


def test_doctor_cannot_change_status(client_as):
    item = make("VENT-001")
    assert act(client_as(Role.DOCTOR), item.pk, "use").status_code == 403
    item.refresh_from_db()
    assert item.status == "available"


def test_other_hospitals_equipment_is_not_found(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    item = make("VENT-001", hospital=city)
    assert act(client_as(Role.NURSE, hospital=seaview), item.pk, "use").status_code == 404
    item.refresh_from_db()
    assert item.status == "available"


def test_staff_without_a_hospital_cannot_change_a_hospitals_equipment(client_as, make_hospital):
    item = make("VENT-001", hospital=make_hospital("City"))
    assert act(client_as(Role.NURSE), item.pk, "use").status_code == 404


def test_admin_can_change_any_hospitals_equipment(client_as, make_hospital):
    item = make("VENT-001", hospital=make_hospital("City"))
    assert act(client_as(Role.ADMIN, hospital=make_hospital("Seaview")), item.pk, "use").status_code == 200


def test_matchable_is_only_available_equipment():
    make("VENT-001", status="available")
    make("VENT-002", status="inUse")
    make("VENT-003", status="maintenance")
    make("VENT-004", status="outOfService")
    make("VENT-005", status="reserved")
    assert list(Equipment.objects.matchable().values_list("identifier", flat=True)) == ["VENT-001"]
