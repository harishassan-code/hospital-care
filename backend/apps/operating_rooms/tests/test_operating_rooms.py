"""Story #28: Operating room registry."""

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.operating_rooms.models import OperatingRoom

pytestmark = pytest.mark.django_db

OR1 = {"name": "OR 1", "capabilities": ["general"], "location": "Block B, floor 2", "status": "available"}


def make(name, capabilities=("general",), status="available", location="Block B", **extra):
    return OperatingRoom.objects.create(
        name=name, capabilities=list(capabilities), location=location, status=status, **extra
    )


def names(response):
    return [room["name"] for room in response.json()]


def act(client, pk, action, **extra):
    return client.post(
        reverse("operating-room-action", args=[pk]), {"action": action, **extra}, format="json"
    )


def test_register_room_with_capabilities_location_and_status(client_as):
    res = client_as(Role.NURSE).post(
        reverse("operating-room-list"),
        {
            **OR1,
            "name": "Cardiac theatre",
            "capabilities": ["trauma", "cardiac", "trauma"],
            "status": "cleaning",
        },
        format="json",
    )
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Cardiac theatre"
    assert data["capabilities"] == ["cardiac", "trauma"]  # de-duplicated and sorted
    assert (data["location"], data["status"]) == ("Block B, floor 2", "cleaning")
    entry = AuditLog.objects.get(action="operatingroom.registered")
    assert entry.target_repr == "Cardiac theatre"
    assert entry.after == {
        "name": "Cardiac theatre",
        "capabilities": ["cardiac", "trauma"],
        "status": "cleaning",
    }


def test_status_defaults_to_available(client_as):
    res = client_as(Role.ADMIN).post(
        reverse("operating-room-list"), {"name": "OR 2", "capabilities": ["general"]}, format="json"
    )
    assert res.status_code == 201 and res.json()["status"] == "available"


def test_room_name_must_be_unique_per_hospital_any_case(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    make("OR 1", hospital=seaview)
    res = client_as(Role.NURSE, hospital=seaview).post(
        reverse("operating-room-list"), {**OR1, "name": "or 1"}, format="json"
    )
    assert res.status_code == 400 and "name" in res.json()
    # Another hospital can use the same name.
    other = client_as(Role.NURSE, hospital=city, email="nurse2@example.com")
    assert other.post(reverse("operating-room-list"), OR1, format="json").status_code == 201


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"capabilities": []}, "capabilities"),
        ({"capabilities": ["laser"]}, "capabilities"),
        ({"capabilities": "cardiac"}, "capabilities"),
        ({"name": "   "}, "name"),
        ({"status": "broken"}, "status"),
    ],
)
def test_registration_is_validated(client_as, change, field):
    res = client_as(Role.ADMIN).post(reverse("operating-room-list"), {**OR1, **change}, format="json")
    assert res.status_code == 400 and field in res.json()
    assert not OperatingRoom.objects.exists()


def test_doctor_can_view_but_not_register(client_as):
    doctor = client_as(Role.DOCTOR)
    assert doctor.get(reverse("operating-room-list")).status_code == 200
    assert doctor.post(reverse("operating-room-list"), OR1, format="json").status_code == 403


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_roles_without_access_get_403(client_as, role):
    assert client_as(role).get(reverse("operating-room-list")).status_code == 403


def test_filter_by_capability_status_and_search(client_as):
    make("OR 1", capabilities=["general"], status="available")
    make("Cardiac theatre", capabilities=["cardiac", "general"], status="inUse")
    make("Trauma theatre", capabilities=["trauma"], status="available", location="Emergency block")
    doctor = client_as(Role.DOCTOR)
    url = reverse("operating-room-list")
    assert names(doctor.get(url, {"capability": "cardiac"})) == ["Cardiac theatre"]
    assert names(doctor.get(url, {"capability": "general"})) == ["Cardiac theatre", "OR 1"]
    assert names(doctor.get(url, {"status": "available"})) == ["OR 1", "Trauma theatre"]
    assert names(doctor.get(url, {"capability": "trauma", "status": "inUse"})) == []
    assert names(doctor.get(url, {"q": "emergency"})) == ["Trauma theatre"]
    assert names(doctor.get(url, {"capability": "bogus"})) == ["Cardiac theatre", "OR 1", "Trauma theatre"]


def test_staff_only_see_their_own_hospitals_rooms(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    make("OR 1", hospital=seaview)
    make("OR 2", hospital=city)
    assert names(client_as(Role.NURSE, hospital=seaview).get(reverse("operating-room-list"))) == ["OR 1"]
    assert (
        len(client_as(Role.ADMIN).get(reverse("operating-room-list")).json()) == 2
    )  # admin without a hospital


@pytest.mark.parametrize(
    ("start", "action", "end"),
    [
        ("available", "startCase", "inUse"),
        ("inUse", "finishCase", "cleaning"),
        ("cleaning", "finishCleaning", "available"),
        ("available", "startMaintenance", "maintenance"),
        ("cleaning", "startMaintenance", "maintenance"),
        ("maintenance", "finishMaintenance", "available"),
        ("available", "outOfService", "outOfService"),
        ("maintenance", "outOfService", "outOfService"),
        ("outOfService", "returnToService", "maintenance"),
        # Story #43: a hold on a room, and its release or use.
        ("available", "reserve", "reserved"),
        ("reserved", "cancelReservation", "available"),
        ("reserved", "startCase", "inUse"),
    ],
)
def test_allowed_moves(client_as, start, action, end):
    room = make("OR 1", status=start)
    res = act(client_as(Role.NURSE), room.pk, action)
    assert res.status_code == 200 and res.json()["status"] == end


def test_status_change_is_saved_and_audit_logged(client_as):
    room = make("OR 1")
    res = act(client_as(Role.NURSE), room.pk, "startCase", reason="Hip replacement")
    assert res.status_code == 200 and res.json()["statusSince"]
    room.refresh_from_db()
    assert room.status == "inUse"
    # The shared change_status helper names the audit action after the model, as for blood units.
    entry = AuditLog.objects.get(action="operatingroom.status_changed")
    assert entry.actor_email == "nurse@example.com" and entry.target_repr == "OR 1"
    assert (entry.before, entry.after, entry.reason) == (
        {"status": "available"},
        {"status": "inUse"},
        "Hip replacement",
    )


def test_refused_move_is_409_and_changes_nothing(client_as):
    room = make("OR 1", status="cleaning")
    res = act(client_as(Role.NURSE), room.pk, "startCase")
    assert res.status_code == 409 and "room that is" in res.json()["detail"]
    room.refresh_from_db()
    assert room.status == "cleaning"
    assert not AuditLog.objects.filter(action="operatingroom.status_changed").exists()


def test_unknown_action_is_400(client_as):
    room = make("OR 1")
    assert act(client_as(Role.NURSE), room.pk, "teleport").status_code == 400


def test_doctor_cannot_change_status(client_as):
    room = make("OR 1")
    assert act(client_as(Role.DOCTOR), room.pk, "startCase").status_code == 403
    room.refresh_from_db()
    assert room.status == "available"


def test_other_hospitals_room_is_not_found(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    room = make("OR 1", hospital=city)
    assert act(client_as(Role.NURSE, hospital=seaview), room.pk, "startCase").status_code == 404
    room.refresh_from_db()
    assert room.status == "available"


def test_staff_without_a_hospital_cannot_change_a_hospitals_room(client_as, make_hospital):
    room = make("OR 1", hospital=make_hospital("City"))
    assert act(client_as(Role.NURSE), room.pk, "startCase").status_code == 404


def test_admin_can_change_any_hospitals_room(client_as, make_hospital):
    room = make("OR 1", hospital=make_hospital("City"))
    assert (
        act(client_as(Role.ADMIN, hospital=make_hospital("Seaview")), room.pk, "startCase").status_code == 200
    )


def test_matchable_is_only_available_rooms():
    make("OR 1", status="available")
    make("OR 2", status="inUse")
    make("OR 3", status="cleaning")
    make("OR 4", status="maintenance")
    make("OR 5", status="outOfService")
    make("OR 6", status="reserved")
    assert list(OperatingRoom.objects.matchable().values_list("name", flat=True)) == ["OR 1"]


def test_with_capability_matches_whole_codes_only():
    make("Cardiac theatre", capabilities=["cardiac"])
    make("Hybrid", capabilities=["cardiac", "neuro"])
    make("Neuro only", capabilities=["neuro"])

    def names_for(code):
        return sorted(OperatingRoom.objects.with_capability(code).values_list("name", flat=True))

    assert names_for("cardiac") == ["Cardiac theatre", "Hybrid"]
    assert names_for("neuro") == ["Hybrid", "Neuro only"]
    assert names_for("card") == []  # a partial code never matches
