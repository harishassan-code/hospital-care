import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.hospitals.models import Bed, BedStatus, Ward

pytestmark = pytest.mark.django_db


@pytest.fixture
def ward():
    return Ward.objects.create(code="icu", name="ICU", kind="Intensive care")


@pytest.fixture
def occupied(ward):
    return Bed.objects.create(
        ward=ward,
        label="ICU-01",
        status=BedStatus.OCCUPIED,
        patient_initials="A.B.",
        patient_age=40,
        patient_sex="F",
        admitted_at=timezone.now(),
        expected_discharge=timezone.localdate(),
        isolation="contact",
    )


def action(client, label, name):
    return client.post(reverse("bed-action", args=[label]), {"action": name}, format="json")


def test_board_matches_frontend_shape(client_as, occupied, ward):
    Bed.objects.create(ward=ward, label="ICU-02")
    data = client_as(Role.DOCTOR).get(reverse("bed-board")).json()
    assert data["wards"] == [{"id": "icu", "name": "ICU", "kind": "Intensive care"}]
    full, empty = data["beds"]
    assert full["id"] == "ICU-01" and full["ward"] == "icu" and full["status"] == "occupied"
    assert full["patient"] == {"initials": "A.B.", "age": 40, "sex": "F"}
    assert {"statusSince", "admittedAt", "expectedDischarge", "isolation"} <= full.keys()
    assert "patient" not in empty and "isolation" not in empty


def test_discharge_clears_patient_and_starts_cleaning(client_as, occupied):
    res = action(client_as(Role.NURSE), "ICU-01", "discharge")
    assert res.status_code == 200 and res.json()["status"] == "cleaning"
    occupied.refresh_from_db()
    assert occupied.patient_initials == "" and occupied.admitted_at is None and occupied.isolation == ""


@pytest.mark.parametrize(
    ("start", "name", "end"),
    [
        ("cleaning", "markReady", "free"),
        ("free", "reserve", "reserved"),
        ("free", "outOfService", "outOfService"),
        ("reserved", "cancelReservation", "free"),
        ("outOfService", "returnToService", "cleaning"),
    ],
)
def test_allowed_transitions(client_as, ward, start, name, end):
    Bed.objects.create(ward=ward, label="X-1", status=start)
    assert action(client_as(Role.ADMIN), "X-1", name).json()["status"] == end


def test_illegal_transition_is_refused(client_as, occupied):
    res = action(client_as(Role.NURSE), "ICU-01", "reserve")
    assert res.status_code == 409
    occupied.refresh_from_db()
    assert occupied.status == BedStatus.OCCUPIED


def test_unknown_action_and_unknown_bed(client_as, occupied):
    nurse = client_as(Role.NURSE)
    assert action(nurse, "ICU-01", "teleport").status_code == 400
    assert action(nurse, "NOPE-9", "discharge").status_code == 404


def test_doctor_can_view_but_not_change_beds(client_as, occupied):
    assert action(client_as(Role.DOCTOR), "ICU-01", "discharge").status_code == 403


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_roles_without_beds_access(client_as, role):
    assert client_as(role).get(reverse("bed-board")).status_code == 403


def test_anonymous_is_refused(api):
    assert api.get(reverse("bed-board")).status_code == 403
