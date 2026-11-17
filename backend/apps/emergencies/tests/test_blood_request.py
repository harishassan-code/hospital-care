"""Story #36: a blood request is an emergency case with one blood need, sent through the case endpoint."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import BloodGroup, Component
from apps.emergencies.models import EmergencyRequest, RequestItem, Severity

pytestmark = pytest.mark.django_db


def blood_request(item=None, severity="critical"):
    default = {"type": "blood", "group": "O-", "component": "redCells", "quantity": 2}
    return {"severity": severity, "items": [default if item is None else item]}


def send(client, body):
    return client.post(reverse("emergency-cases"), body, format="json")


# ── Validation: the blood path refuses what it should ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"quantity": 0}, "quantity"),
        ({"quantity": -1}, "quantity"),
        ({"quantity": 2.5}, "quantity"),
        ({"quantity": "two"}, "quantity"),
        ({"quantity": 21}, "quantity"),
        ({"component": "bogus"}, "component"),
        ({"component": "whole_blood"}, "component"),
        ({"group": "Z+"}, "group"),
        ({"group": ""}, "group"),
        ({"component": None}, "component"),
        ({"group": None}, "group"),
    ],
)
def test_a_blood_request_with_a_bad_value_is_400_and_saves_nothing(client_as, changes, field):
    item = {"type": "blood", "group": "O-", "component": "redCells", "quantity": 2, **changes}

    res = send(client_as(Role.DOCTOR), blood_request(item))

    assert res.status_code == 400
    assert field in res.json()["items"]["0"]
    assert not EmergencyRequest.objects.exists() and not RequestItem.objects.exists()


@pytest.mark.parametrize("missing", ["group", "component", "quantity"])
def test_a_blood_request_missing_a_field_is_400(client_as, missing):
    item = {"type": "blood", "group": "O-", "component": "redCells", "quantity": 2}
    del item[missing]

    res = send(client_as(Role.NURSE), blood_request(item))

    assert res.status_code == 400
    assert missing in res.json()["items"]["0"]
    assert not EmergencyRequest.objects.exists()


def test_every_supported_group_and_component_is_accepted(client_as):
    nurse = client_as(Role.NURSE)
    for group in BloodGroup.values:
        for component in Component.values:
            item = {"type": "blood", "group": group, "component": component, "quantity": 1}
            assert send(nurse, blood_request(item)).status_code == 201
    assert EmergencyRequest.objects.count() == len(BloodGroup.values) * len(Component.values)


def test_the_largest_blood_request_is_20_units(client_as):
    doctor = client_as(Role.DOCTOR)
    edge = {"type": "blood", "group": "O-", "component": "redCells", "quantity": 20}
    assert send(doctor, blood_request(edge)).status_code == 201


# ── A valid request ─────────────────────────────────────────────────────────────────────────────


def test_a_valid_blood_request_is_201_with_reference_open_status_and_a_history_entry(
    client_as, make_hospital
):
    hospital = make_hospital()
    doctor = client_as(Role.DOCTOR, hospital=hospital)

    res = send(
        doctor, blood_request({"type": "blood", "group": "AB+", "component": "platelets", "quantity": 3})
    )

    assert res.status_code == 201
    data = res.json()
    assert data["id"] == f"EC-{timezone.localdate().year}-0001"
    assert data["status"] == "open" and data["severity"] == "critical"
    assert data["hospital"] == {"id": hospital.pk, "name": hospital.name}
    assert data["items"] == [{"type": "blood", "group": "AB+", "component": "platelets", "quantity": 3}]
    [entry] = EmergencyRequest.objects.get(reference=data["id"]).history.all()
    assert (entry.from_status, entry.to_status, entry.action) == ("", "open", "create")


def test_a_valid_blood_request_is_audit_logged(client_as):
    reference = send(client_as(Role.DOCTOR), blood_request()).json()["id"]

    entry = AuditLog.objects.get(action="emergencyrequest.created")
    assert entry.target_repr == reference
    assert entry.after == {"severity": "critical", "status": "open", "items": 1}


@pytest.mark.parametrize("severity", Severity.values)
def test_urgency_is_the_case_severity(client_as, severity):
    res = send(client_as(Role.NURSE), blood_request(severity=severity))

    assert res.status_code == 201 and res.json()["severity"] == severity
    assert EmergencyRequest.objects.get().severity == severity


def test_a_blood_request_takes_no_patient_data(client_as):
    res = send(client_as(Role.NURSE), blood_request())

    assert res.json()["patientRef"] == ""
