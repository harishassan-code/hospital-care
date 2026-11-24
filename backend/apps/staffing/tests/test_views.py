"""Staff on duty (B22): who is on now against the rota, who is missing, and nurse ratios; clock in or mark
absent."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.hospitals.models import Bed, BedStatus, Department, Ward
from apps.staffing.models import Shift, StaffMember

pytestmark = pytest.mark.django_db
URL = reverse("staffing")


@pytest.fixture
def rota(make_hospital):
    hospital = make_hospital()
    gm = Department.objects.create(hospital=hospital, name="General medicine")
    ward = Ward.objects.create(
        code="medA", hospital=hospital, department=gm, name="Medical A", kind="General"
    )
    for n in range(10):
        Bed.objects.create(label=f"MA-{n}", ward=ward, status=BedStatus.OCCUPIED)
    now = timezone.now()
    shifts = {}
    for name, role, clocked in [
        ("Nurse On", "nurse", True),
        ("Nurse Missing", "nurse", False),
        ("Dr. On", "doctor", True),
    ]:
        member = StaffMember.objects.create(
            hospital=hospital, name=name, role=role, department="General medicine"
        )
        shifts[name] = Shift.objects.create(
            staff=member,
            hospital=hospital,
            starts_at=now - timedelta(hours=2),
            ends_at=now + timedelta(hours=6),
            clocked_in_at=now - timedelta(hours=2) if clocked else None,
        )
    return hospital, shifts


def test_on_duty_against_the_rota_with_who_is_missing(client_as, rota):
    hospital, _ = rota
    body = client_as(Role.DOCTOR, hospital=hospital).get(URL).json()
    assert body["summary"]["nurse"] == {"planned": 2, "onDuty": 1, "missing": 1}
    assert body["summary"]["doctor"]["onDuty"] == 1
    statuses = {p["name"]: p["status"] for p in body["people"]}
    assert statuses == {"Nurse On": "onDuty", "Nurse Missing": "missing", "Dr. On": "onDuty"}
    assert all(p["actions"] == [] for p in body["people"])  # doctors view only
    [ratio] = body["ratios"]
    assert ratio == {
        "department": "General medicine",
        "patients": 10,
        "nurses": 1,
        "patientsPerNurse": 10.0,
        "target": 8,
        "short": True,
    }
    assert len(body["day"]) == 24


def test_the_nurse_in_charge_marks_someone_absent_or_clocks_them_in(client_as, rota):
    hospital, shifts = rota
    nurse = client_as(Role.NURSE, hospital=hospital)
    missing = shifts["Nurse Missing"]
    url = reverse("staffing-shift-action", args=[missing.pk])
    body = nurse.post(url, {"action": "markAbsent"}, format="json").json()
    assert body["status"] == "absent" and body["actions"] == []
    assert AuditLog.objects.filter(action="shift.marked_absent").exists()
    assert nurse.post(url, {"action": "clockIn"}, format="json").status_code == 409
    on = reverse("staffing-shift-action", args=[shifts["Nurse On"].pk])
    assert nurse.post(on, {"action": "markAbsent"}, format="json").status_code == 409


def test_another_hospitals_shift_is_a_404(client_as, rota, make_hospital):
    _, shifts = rota
    other = client_as(Role.NURSE, hospital=make_hospital(name="Seaview Hospital"))
    url = reverse("staffing-shift-action", args=[shifts["Nurse Missing"].pk])
    assert other.post(url, {"action": "clockIn"}).status_code == 404


@pytest.mark.parametrize(
    ("role", "code"), [(Role.BLOOD_BANK, 403), (Role.PHARMACIST, 403), (Role.PATIENT, 403)]
)
def test_only_clinical_staff_and_admins_see_it(client_as, make_hospital, role, code):
    hospital = make_hospital()
    extra = {} if role == Role.PATIENT else {"hospital": hospital}
    assert client_as(role, **extra).get(URL).status_code == code
