"""Story #50: Ambulance registry."""

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.ambulances.models import Ambulance, AmbulanceStatus

pytestmark = pytest.mark.django_db

AMB = {"identifier": "amb-7", "type": "basic"}


def make(identifier, type_="basic", status="available", **extra):
    return Ambulance.objects.create(identifier=identifier, ambulance_type=type_, status=status, **extra)


def test_register_ambulance(client_as):
    res = client_as(Role.NURSE).post(reverse("ambulance-list"), AMB, format="json")
    assert res.status_code == 201
    data = res.json()
    assert data["identifier"] == "AMB-7"
    assert (data["type"], data["status"]) == ("basic", "available")
    assert AuditLog.objects.filter(action="ambulance.registered").count() == 1


def test_filter_by_type_and_status(client_as):
    make("AMB-1", status=AmbulanceStatus.AVAILABLE)
    make("AMB-2", type_="advanced", status=AmbulanceStatus.MAINTENANCE)
    nurse = client_as(Role.NURSE)
    url = reverse("ambulance-list")
    assert nurse.get(url, {"status": "available"}).json()[0]["identifier"] == "AMB-1"
    assert nurse.get(url, {"type": "advanced"}).json()[0]["identifier"] == "AMB-2"