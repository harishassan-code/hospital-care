"""The emergency department queue page (B22): own hospital only, never a name, and every move through the
visit's lifecycle, audit-logged."""

import random

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.models import ErVisit, VisitStatus
from apps.emergencies.visits import arrive
from apps.hospitals.models import Bed, BedStatus, BedType, Department, Ward

pytestmark = pytest.mark.django_db
URL = reverse("emergency-queue")


def action_url(visit):
    return reverse("emergency-queue-action", args=[visit.pk])


@pytest.fixture
def department(make_hospital):
    hospital = make_hospital()
    em = Department.objects.create(hospital=hospital, name="Emergency medicine")
    ed = Ward.objects.create(code="ed", hospital=hospital, department=em, name="Emergency", kind="Emergency")
    med = Ward.objects.create(code="medA", hospital=hospital, name="Medical A", kind="General medicine")
    Bed.objects.create(label="ED-01", ward=ed, bed_type=BedType.EMERGENCY)
    Bed.objects.create(label="MA-01", ward=med)
    return hospital


def patient(hospital, triage=3, **extra):
    fields = {"age_band": "40-64", "sex": "M", "complaint": "cardiac", **extra}
    return arrive(hospital=hospital, triage=triage, actor=None, rand=random.Random(1), **fields)


def test_the_queue_shows_tags_and_categories_never_names(client_as, department):
    patient(department)
    body = client_as(Role.NURSE, hospital=department).get(URL).json()
    [row] = body["visits"]
    assert row["tag"].startswith("ED-") and row["triage"] == 3 and row["ageBand"] == "40-64"
    assert "name" not in row and row["actions"] == ["startTreatment", "leaveUnseen"]
    assert body["beds"] == {"total": 1, "free": 1}


def test_start_treatment_then_admit_moves_the_patient_to_a_ward_bed(client_as, department):
    visit = patient(department)
    nurse = client_as(Role.NURSE, hospital=department)
    started = nurse.post(action_url(visit), {"action": "startTreatment"}, format="json").json()
    assert started["status"] == "treating" and started["bed"] == "ED-01"
    admitted = nurse.post(action_url(visit), {"action": "admit"}, format="json").json()
    assert admitted["status"] == "left"
    assert Bed.objects.get(label="MA-01").status == BedStatus.OCCUPIED
    assert Bed.objects.get(label="ED-01").status == BedStatus.CLEANING
    assert ErVisit.objects.get(pk=visit.pk).handled_by is not None  # the simulation leaves it to staff
    assert AuditLog.objects.filter(action="ervisit.admitted", target_id=str(visit.pk)).exists()


def test_no_ward_bed_keeps_the_patient_waiting_in_the_department(client_as, department):
    visit = patient(department)
    Bed.objects.filter(label="MA-01").update(status=BedStatus.OCCUPIED)
    nurse = client_as(Role.NURSE, hospital=department)
    nurse.post(action_url(visit), {"action": "startTreatment"}, format="json")
    assert nurse.post(action_url(visit), {"action": "admit"}, format="json").json()["status"] == "boarding"
    again = nurse.post(action_url(visit), {"action": "admit"}, format="json")
    assert again.status_code == 409


def test_no_emergency_bed_free_is_a_409_for_an_urgent_patient(client_as, department):
    Bed.objects.filter(label="ED-01").update(status=BedStatus.OCCUPIED)
    visit = patient(department, triage=2)
    response = client_as(Role.DOCTOR, hospital=department).post(
        action_url(visit), {"action": "startTreatment"}
    )
    assert response.status_code == 409
    assert ErVisit.objects.get(pk=visit.pk).status == VisitStatus.WAITING


def test_a_minor_complaint_can_be_seen_in_a_chair(client_as, department):
    Bed.objects.filter(label="ED-01").update(status=BedStatus.OCCUPIED)
    visit = patient(department, triage=5, complaint="minor")
    body = (
        client_as(Role.NURSE, hospital=department)
        .post(action_url(visit), {"action": "startTreatment"})
        .json()
    )
    assert body["status"] == "treating" and body["bed"] is None


def test_another_hospitals_patient_is_a_404(client_as, department, make_hospital):
    visit = patient(department)
    other = make_hospital(name="Seaview Hospital")
    nurse = client_as(Role.NURSE, hospital=other)
    assert nurse.post(action_url(visit), {"action": "leaveUnseen"}).status_code == 404
    assert nurse.get(URL).json()["visits"] == []


@pytest.mark.parametrize(
    ("role", "code"), [(Role.BLOOD_BANK, 403), (Role.PHARMACIST, 403), (Role.PATIENT, 403)]
)
def test_only_clinical_staff_open_the_queue(client_as, department, role, code):
    extra = {} if role == Role.PATIENT else {"hospital": department}
    assert client_as(role, **extra).get(URL).status_code == code
