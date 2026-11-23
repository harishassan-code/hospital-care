"""A hospital's own emergency department status (B19): staff at that hospital read and update it; the change
is
audit-logged; the old single-row status becomes the first hospital's."""

import importlib

import pytest
from django.apps import apps as django_apps
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.models import EmergencyStatus, ErStatus
from apps.matching.tests.reservation_support import staff

pytestmark = pytest.mark.django_db

URL = reverse("emergency-department")


def signed_in(client, user):
    client.force_authenticate(user)
    return client


@pytest.fixture
def general(make_hospital):
    return make_hospital("General")


def test_a_hospital_that_never_reported_reads_as_nulls(api, make_user, general):
    nurse = staff(make_user, general)
    data = signed_in(api, nurse).get(URL).json()
    assert data == {"status": None, "waitMinutes": None, "waitingCount": None, "updatedAt": None}


@pytest.mark.parametrize("role", [Role.NURSE, Role.DOCTOR, Role.ADMIN])
def test_staff_who_treat_patients_update_their_own_department(api, make_user, general, role):
    user = staff(make_user, general, role)
    res = signed_in(api, user).put(
        URL, {"status": "busy", "waitMinutes": 75, "waitingCount": 18}, format="json"
    )
    assert res.status_code == 200, res.content
    assert res.json()["status"] == "busy" and res.json()["updatedAt"]
    saved = EmergencyStatus.objects.get(hospital=general)
    assert (saved.status, saved.wait_minutes, saved.waiting_count) == (ErStatus.BUSY, 75, 18)


def test_the_change_is_audit_logged_with_before_and_after(api, make_user, general):
    nurse = staff(make_user, general)
    client = signed_in(api, nurse)
    client.put(URL, {"status": "accepting", "waitMinutes": 20, "waitingCount": 4}, format="json")
    client.put(URL, {"status": "diverting", "waitMinutes": 90, "waitingCount": 30}, format="json")
    client.put(
        URL, {"status": "diverting", "waitMinutes": 90, "waitingCount": 30}, format="json"
    )  # no change

    entries = AuditLog.objects.filter(action="er_status.updated").order_by("id")
    assert entries.count() == 2
    first, second = entries
    assert first.before is None and first.target_id == str(general.pk)
    assert second.before["status"] == "accepting" and second.after["status"] == "diverting"
    assert second.actor_email == nurse.email


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST])
def test_roles_that_only_view_cases_can_read_but_not_change_it(api, make_user, general, role):
    user = staff(make_user, general, role)
    client = signed_in(api, user)
    assert client.get(URL).status_code == 200
    res = client.put(URL, {"status": "busy", "waitMinutes": 75, "waitingCount": 18}, format="json")
    assert res.status_code == 403
    assert not EmergencyStatus.objects.exists()


def test_patients_and_strangers_are_refused(api, client_as):
    assert api.get(URL).status_code in (401, 403)
    assert client_as(Role.PATIENT).get(URL).status_code == 403


def test_staff_without_a_hospital_have_no_department(client_as):
    assert client_as(Role.ADMIN).get(URL).status_code == 404


def test_it_only_ever_changes_the_users_own_hospital(api, make_user, make_hospital, general):
    other = make_hospital("Other")
    EmergencyStatus.objects.create(
        hospital=other, status=ErStatus.ACCEPTING, wait_minutes=10, waiting_count=2
    )
    nurse = staff(make_user, general)
    signed_in(api, nurse).put(
        URL, {"status": "busy", "waitMinutes": 60, "waitingCount": 9, "hospital": other.pk}, format="json"
    )
    assert EmergencyStatus.objects.get(hospital=other).status == ErStatus.ACCEPTING
    assert EmergencyStatus.objects.get(hospital=general).status == ErStatus.BUSY


@pytest.mark.parametrize(
    "body",
    [
        {"status": "closed", "waitMinutes": 10, "waitingCount": 1},
        {"status": "busy", "waitMinutes": -1, "waitingCount": 1},
        {"status": "busy", "waitMinutes": 24 * 60 + 1, "waitingCount": 1},
        {"status": "busy", "waitMinutes": 10, "waitingCount": 1000},
        {"status": "busy", "waitMinutes": 10},
    ],
)
def test_bad_values_are_refused_and_change_nothing(api, make_user, general, body):
    nurse = staff(make_user, general)
    assert signed_in(api, nurse).put(URL, body, format="json").status_code == 400
    assert not EmergencyStatus.objects.exists()


# ── The migration (0007) ────────────────────────────────────────────────────────────────────────────────

migration = importlib.import_module("apps.emergencies.migrations.0007_emergency_status_per_hospital")


def test_the_old_single_row_goes_to_the_first_hospital(make_hospital):
    first, second = make_hospital("First"), make_hospital("Second")
    EmergencyStatus.objects.create(hospital=second, status=ErStatus.BUSY, wait_minutes=40, waiting_count=12)
    EmergencyStatus.objects.create(hospital=first, status=ErStatus.ACCEPTING, wait_minutes=5, waiting_count=1)

    migration.give_row_to_first_hospital(django_apps, None)

    [row] = EmergencyStatus.objects.all()
    assert row.hospital == first and row.wait_minutes == 40  # the oldest row, now the first hospital's
