"""Story #50: Ambulance registry (B04). Registration, status moves, access and the audit trail."""

import pytest
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.ambulances.models import Ambulance
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db

ADVANCED = {"identifier": "amb-04", "type": "advanced"}


def make(identifier, type_="advanced", status="available", **extra):
    return Ambulance.objects.create(identifier=identifier, type=type_, status=status, **extra)


def ids(response):
    return [a["identifier"] for a in response.json()]


def act(client, pk, action, **extra):
    return client.post(reverse("ambulance-action", args=[pk]), {"action": action, **extra}, format="json")


def register(client, body):
    return client.post(reverse("ambulance-list"), body, format="json")


# Registration


def test_register_at_own_hospital_upper_cases_the_tag_and_starts_available(client_as, make_hospital):
    seaview = make_hospital("Seaview")
    res = register(client_as(Role.NURSE, hospital=seaview), {"identifier": " amb-04 ", "type": "advanced"})
    assert res.status_code == 201
    data = res.json()
    assert (data["identifier"], data["type"], data["status"], data["hospital"]) == (
        "AMB-04",
        "advanced",
        "available",
        "Seaview",
    )
    assert data["statusSince"]
    entry = AuditLog.objects.get(action="ambulance.registered")
    assert entry.actor_email == "nurse@example.com"
    assert entry.target_repr == "AMB-04 (Advanced life support)"
    assert entry.after == {"identifier": "AMB-04", "type": "advanced", "status": "available"}


def test_client_cannot_set_the_status_on_register(client_as, make_hospital):
    res = register(client_as(Role.ADMIN, hospital=make_hospital()), {**ADVANCED, "status": "outOfService"})
    assert res.status_code == 201 and res.json()["status"] == "available"


def test_admin_registers_at_the_hospital_they_pick(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    res = register(client_as(Role.ADMIN, hospital=city), {**ADVANCED, "hospitalId": seaview.pk})
    assert res.status_code == 201 and res.json()["hospital"] == "Seaview"


def test_non_admin_cannot_register_at_another_hospital(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    res = register(client_as(Role.NURSE, hospital=seaview), {**ADVANCED, "hospitalId": city.pk})
    assert res.status_code == 201 and res.json()["hospital"] == "Seaview"
    assert Ambulance.objects.get().hospital == seaview


def test_admin_without_a_hospital_must_pick_one(client_as):
    res = register(client_as(Role.ADMIN), ADVANCED)
    assert res.status_code == 400 and "hospitalId" in res.json()
    assert not Ambulance.objects.exists()


def test_nurse_without_a_hospital_gets_a_hospital_error(client_as):
    res = register(client_as(Role.NURSE), ADVANCED)
    assert res.status_code == 400 and "hospitalId" in res.json()
    assert not AuditLog.objects.filter(action="ambulance.registered").exists()


def test_unknown_or_deactivated_hospital_is_a_hospital_error(client_as, make_hospital):
    closed = make_hospital("Old Town", is_active=False)
    admin = client_as(Role.ADMIN)
    for hospital_id in (9999, closed.pk):
        res = register(admin, {**ADVANCED, "hospitalId": hospital_id})
        assert res.status_code == 400 and "hospitalId" in res.json()
    assert not Ambulance.objects.exists()


def test_tag_must_be_unique_within_a_hospital_any_case(client_as, make_hospital):
    seaview = make_hospital("Seaview")
    make("AMB-04", hospital=seaview)
    res = register(client_as(Role.NURSE, hospital=seaview), {**ADVANCED, "identifier": "amb-04"})
    assert res.status_code == 400 and "identifier" in res.json()
    assert Ambulance.objects.count() == 1
    assert not AuditLog.objects.filter(action="ambulance.registered").exists()


def test_another_hospital_can_use_the_same_tag(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    make("AMB-04", hospital=seaview)
    res = register(client_as(Role.NURSE, hospital=city, email="nurse2@example.com"), ADVANCED)
    assert res.status_code == 201


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="SQLite skips constraints with nulls_distinct=False"
)
def test_database_constraint_refuses_a_duplicate_tag_in_any_case(make_hospital):
    seaview = make_hospital("Seaview")
    make("AMB-04", hospital=seaview)
    with pytest.raises(IntegrityError), transaction.atomic():
        make("amb-04", hospital=seaview)


@pytest.mark.parametrize(
    ("change", "field"),
    [({"type": "toaster"}, "type"), ({"identifier": "  "}, "identifier"), ({"identifier": ""}, "identifier")],
)
def test_registration_is_validated(client_as, make_hospital, change, field):
    res = register(client_as(Role.ADMIN, hospital=make_hospital()), {**ADVANCED, **change})
    assert res.status_code == 400 and field in res.json()
    assert not Ambulance.objects.exists()


# Listing


def test_filters_by_type_status_and_tag(client_as, make_hospital):
    seaview = make_hospital("Seaview")
    make("AMB-01", "advanced", hospital=seaview)
    make("AMB-02", "basic", "maintenance", hospital=seaview)
    make("AMB-03", "patientTransport", hospital=seaview)
    doctor = client_as(Role.DOCTOR, hospital=seaview)
    url = reverse("ambulance-list")
    assert ids(doctor.get(url)) == ["AMB-01", "AMB-02", "AMB-03"]  # by type, then tag
    assert ids(doctor.get(url, {"type": "advanced"})) == ["AMB-01"]
    assert ids(doctor.get(url, {"type": "toaster"})) == [
        "AMB-01",
        "AMB-02",
        "AMB-03",
    ]  # unknown filters are ignored
    assert ids(doctor.get(url, {"status": "maintenance"})) == ["AMB-02"]
    assert ids(doctor.get(url, {"type": "patientTransport", "status": "available"})) == ["AMB-03"]
    assert ids(doctor.get(url, {"q": " amb-02 "})) == ["AMB-02"]
    assert ids(doctor.get(url, {"q": "03"})) == ["AMB-03"]


def test_staff_only_see_their_own_hospitals_ambulances(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    make("AMB-01", hospital=seaview)
    make("AMB-02", hospital=city)
    url = reverse("ambulance-list")
    assert ids(client_as(Role.NURSE, hospital=seaview).get(url)) == ["AMB-01"]
    assert ids(client_as(Role.ADMIN, hospital=seaview).get(url)) == ["AMB-01", "AMB-02"]  # admins get all
    assert len(client_as(Role.ADMIN, email="admin2@example.com").get(url).json()) == 2


def test_user_without_a_hospital_sees_no_ambulances(client_as, make_hospital):
    make("AMB-01", hospital=make_hospital("Seaview"))
    assert client_as(Role.NURSE).get(reverse("ambulance-list")).json() == []


def test_doctor_can_view_but_not_register(client_as, make_hospital):
    doctor = client_as(Role.DOCTOR, hospital=make_hospital())
    assert doctor.get(reverse("ambulance-list")).status_code == 200
    assert register(doctor, ADVANCED).status_code == 403
    assert not Ambulance.objects.exists()


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_roles_without_ambulance_access_get_403(client_as, make_hospital, role):
    staff = client_as(role, hospital=make_hospital())
    assert staff.get(reverse("ambulance-list")).status_code == 403
    assert register(staff, ADVANCED).status_code == 403


def test_signed_out_visitors_get_403(make_hospital):
    item = make("AMB-01", hospital=make_hospital())
    anonymous = APIClient()
    assert anonymous.get(reverse("ambulance-list")).status_code == 403
    assert register(anonymous, ADVANCED).status_code == 403
    assert act(anonymous, item.pk, "startMaintenance").status_code == 403
    item.refresh_from_db()
    assert item.status == "available"


# Status moves (story #50 rules table)


@pytest.mark.parametrize(
    ("start", "action", "end"),
    [
        ("available", "startMaintenance", "maintenance"),
        ("maintenance", "finishMaintenance", "available"),
        ("available", "outOfService", "outOfService"),
        ("maintenance", "outOfService", "outOfService"),
        ("outOfService", "returnToService", "maintenance"),
    ],
)
def test_allowed_moves_save_and_audit_the_change(client_as, make_hospital, start, action, end):
    hospital = make_hospital()
    item = make("AMB-01", status=start, hospital=hospital)
    res = act(client_as(Role.NURSE, hospital=hospital), item.pk, action, reason="Brake check")
    assert res.status_code == 200
    assert res.json()["status"] == end and res.json()["statusSince"]
    item.refresh_from_db()
    assert item.status == end
    entry = AuditLog.objects.get(action="ambulance.status_changed")
    assert entry.target_repr == "AMB-01 (Advanced life support)"
    assert (entry.before, entry.after, entry.reason) == ({"status": start}, {"status": end}, "Brake check")


@pytest.mark.parametrize(
    ("start", "action", "message"),
    [
        ("available", "finishMaintenance", "Can't finishMaintenance a vehicle that is available."),
        ("available", "returnToService", "Can't returnToService a vehicle that is available."),
        ("maintenance", "startMaintenance", "Can't startMaintenance a vehicle that is in maintenance."),
        ("outOfService", "startMaintenance", "Can't startMaintenance a vehicle that is out of service."),
        ("outOfService", "outOfService", "Can't outOfService a vehicle that is out of service."),
    ],
)
def test_refused_move_is_409_with_the_machine_message_and_changes_nothing(
    client_as, make_hospital, start, action, message
):
    hospital = make_hospital()
    item = make("AMB-01", status=start, hospital=hospital)
    res = act(client_as(Role.NURSE, hospital=hospital), item.pk, action)
    assert res.status_code == 409 and res.json() == {"detail": message}
    item.refresh_from_db()
    assert item.status == start
    assert not AuditLog.objects.filter(action="ambulance.status_changed").exists()


@pytest.mark.parametrize("action", ["use", "teleport"])
def test_unknown_action_is_400(client_as, make_hospital, action):
    hospital = make_hospital()
    item = make("AMB-01", hospital=hospital)
    assert act(client_as(Role.NURSE, hospital=hospital), item.pk, action).status_code == 400


def test_admin_can_move_any_hospitals_ambulance(client_as, make_hospital):
    item = make("AMB-01", hospital=make_hospital("City"))
    assert (
        act(client_as(Role.ADMIN, hospital=make_hospital("Seaview")), item.pk, "outOfService").status_code
        == 200
    )


def test_doctor_cannot_change_status(client_as, make_hospital):
    hospital = make_hospital()
    item = make("AMB-01", hospital=hospital)
    assert act(client_as(Role.DOCTOR, hospital=hospital), item.pk, "outOfService").status_code == 403
    item.refresh_from_db()
    assert item.status == "available"
    assert not AuditLog.objects.filter(action="ambulance.status_changed").exists()


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST])
def test_roles_without_access_cannot_change_status(client_as, make_hospital, role):
    hospital = make_hospital()
    item = make("AMB-01", hospital=hospital)
    assert act(client_as(role, hospital=hospital), item.pk, "outOfService").status_code == 403


def test_other_hospitals_ambulance_is_not_found_for_non_admins(client_as, make_hospital):
    seaview, city = make_hospital("Seaview"), make_hospital("City")
    item = make("AMB-01", hospital=city)
    assert act(client_as(Role.NURSE, hospital=seaview), item.pk, "outOfService").status_code == 404
    item.refresh_from_db()
    assert item.status == "available"


def test_staff_without_a_hospital_cannot_change_a_hospitals_ambulance(client_as, make_hospital):
    item = make("AMB-01", hospital=make_hospital("City"))
    assert act(client_as(Role.NURSE), item.pk, "outOfService").status_code == 404


def test_unknown_ambulance_is_not_found(client_as, make_hospital):
    assert act(client_as(Role.NURSE, hospital=make_hospital()), 9999, "outOfService").status_code == 404
