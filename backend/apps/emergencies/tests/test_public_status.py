from datetime import time

import pytest
from django.urls import reverse

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
