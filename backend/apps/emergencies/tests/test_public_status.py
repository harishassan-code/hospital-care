from datetime import time

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.emergencies.models import EmergencyStatus
from apps.hospitals.models import DoctorShift

pytestmark = pytest.mark.django_db


def test_public_status_needs_no_login_and_matches_frontend_shape(api):
    EmergencyStatus.objects.create(pk=1, status="busy", wait_minutes=40, waiting_count=12)
    DoctorShift.objects.create(
        name="Dr. Usman Farooq", department="Emergency medicine", start=time(20), end=time(8)
    )
    DoctorShift.objects.create(name="Dr. Gone", department="X", start=time(9), end=time(10), is_active=False)

    data = api.get(reverse("public-status")).json()
    assert data["emergency"] == {"status": "busy", "waitMinutes": 40, "waitingCount": 12}
    assert "updatedAt" in data
    [doctor] = data["doctors"]
    assert doctor["start"] == "20:00" and doctor["end"] == "08:00" and doctor["id"].startswith("d")


def test_public_status_works_on_an_empty_database(api):
    assert api.get(reverse("public-status")).status_code == 200


# #122 (B13 finding F5): staff names only for signed-in staff.


def make_shift():
    return DoctorShift.objects.create(
        name="Dr. Usman Farooq", department="Emergency medicine", start=time(20), end=time(8)
    )


def test_the_public_sees_departments_and_hours_but_no_names(api):
    make_shift()
    data = api.get(reverse("public-status")).json()
    assert data["namesShown"] is False
    [doctor] = data["doctors"]
    assert doctor["name"] is None
    assert (doctor["department"], doctor["start"], doctor["end"]) == ("Emergency medicine", "20:00", "08:00")


def test_signed_in_staff_see_the_names(client_as):
    make_shift()
    data = client_as(Role.NURSE).get(reverse("public-status")).json()
    assert data["namesShown"] is True
    assert data["doctors"][0]["name"] == "Dr. Usman Farooq"


def test_a_signed_in_patient_sees_no_names(client_as):
    make_shift()
    data = client_as(Role.PATIENT).get(reverse("public-status")).json()
    assert data["namesShown"] is False and data["doctors"][0]["name"] is None
