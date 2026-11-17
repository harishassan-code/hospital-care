"""Stories #30 (create an emergency case) and #32 (its blood and bed needs)."""

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.models import EmergencyRequest, RequestItem
from apps.emergencies.services import next_reference

pytestmark = pytest.mark.django_db

BLOOD = {"type": "blood", "group": "O-", "component": "redCells", "quantity": 4}
BED = {"type": "bed", "bedType": "icu", "quantity": 1}
CASE = {"severity": "critical", "items": [BLOOD, BED]}


def year() -> int:
    return timezone.localdate().year


def create(client, body=None):
    return client.post(reverse("emergency-cases"), body or CASE, format="json")


# ── #30 Create emergency case ───────────────────────────────────────────────────────────────────


def test_a_new_case_is_open_with_a_unique_reference_and_its_needs(client_as, make_hospital):
    hospital = make_hospital()
    doctor = client_as(Role.DOCTOR, hospital=hospital)

    res = create(doctor)

    assert res.status_code == 201
    data = res.json()
    assert data["id"] == f"EC-{year()}-0001"
    assert data["status"] == "open" and data["severity"] == "critical"
    assert data["hospital"] == {"id": hospital.pk, "name": hospital.name}
    assert data["items"] == [BLOOD, BED]
    assert create(doctor).json()["id"] == f"EC-{year()}-0002"


def test_no_patient_identifying_data_is_needed(client_as):
    res = create(client_as(Role.NURSE), {"severity": "moderate", "items": [BED]})
    assert res.status_code == 201 and res.json()["patientRef"] == ""


def test_patient_reference_is_optional_and_short(client_as):
    nurse = client_as(Role.NURSE)
    assert create(nurse, {**CASE, "patientRef": "  Bay 4 / T-17  "}).json()["patientRef"] == "Bay 4 / T-17"
    assert create(nurse, {**CASE, "patientRef": "x" * 31}).status_code == 400


def test_opening_a_case_is_audit_logged(client_as):
    reference = create(client_as(Role.DOCTOR)).json()["id"]
    entry = AuditLog.objects.get(action="emergencyrequest.created")
    assert entry.target_repr == reference and entry.actor_email == "doctor@example.com"
    assert entry.after == {"severity": "critical", "status": "open", "items": 2}


def test_references_continue_from_the_years_highest_and_restart_each_year():
    EmergencyRequest.objects.create(reference=f"EC-{year()}-0041", severity="high")
    EmergencyRequest.objects.create(reference=f"EC-{year() - 1}-0900", severity="high")
    assert next_reference(year()) == f"EC-{year()}-0042"
    assert next_reference(year() + 1) == f"EC-{year() + 1}-0001"
    EmergencyRequest.objects.create(reference=f"EC-{year()}-9999", severity="high")
    assert next_reference(year()) == f"EC-{year()}-10000"  # grows past 4 digits instead of wrapping


# ── #32 Requirements: blood and beds ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"severity": "critical", "items": []}, "items"),
        ({"severity": "critical"}, "items"),
        ({"severity": "panic", "items": [BED]}, "severity"),
        ({"severity": "critical", "items": [BED] * 11}, "items"),
    ],
)
def test_a_case_needs_a_severity_and_one_to_ten_needs(client_as, body, field):
    res = create(client_as(Role.DOCTOR), body)
    assert res.status_code == 400 and field in res.json()
    assert not EmergencyRequest.objects.exists()


@pytest.mark.parametrize(
    ("item", "field"),
    [
        ({"type": "blood", "component": "redCells", "quantity": 2}, "group"),
        ({"type": "blood", "group": "O-", "quantity": 2}, "component"),
        ({"type": "blood", "group": "Z+", "component": "redCells", "quantity": 2}, "group"),
        ({"type": "blood", "group": "O-", "component": "redCells", "quantity": 21}, "quantity"),
        ({"type": "bed", "quantity": 1}, "bedType"),
        ({"type": "bed", "bedType": "icu", "quantity": 6}, "quantity"),
        ({"type": "bed", "bedType": "icu", "quantity": 0}, "quantity"),
        ({"type": "xray", "quantity": 1}, "type"),
        ({"type": "equipment", "quantity": 1}, "equipmentType"),
        ({"type": "equipment", "equipmentType": "toaster", "quantity": 1}, "equipmentType"),
        ({"type": "equipment", "equipmentType": "ventilator", "quantity": 6}, "quantity"),
        ({"type": "operatingRoom", "quantity": 1}, "capability"),
        ({"type": "operatingRoom", "capability": "dental", "quantity": 1}, "capability"),
        ({"type": "operatingRoom", "capability": "cardiac", "quantity": 4}, "quantity"),
    ],
)
def test_each_need_is_validated_for_its_type(client_as, item, field):
    res = create(client_as(Role.DOCTOR), {"severity": "high", "items": [item]})
    assert res.status_code == 400
    assert field in res.json()["items"]["0"]  # DRF keys nested list errors by index


def test_a_bed_need_ignores_blood_fields_sent_with_it(client_as):
    create(client_as(Role.DOCTOR), {"severity": "high", "items": [{**BED, "group": "O-"}]})
    item = RequestItem.objects.get()
    assert (item.resource_type, item.bed_type, item.blood_group, item.fulfilled) == ("bed", "icu", "", 0)


def test_equipment_and_operating_room_needs_are_stored_with_only_their_own_field(client_as):
    """Story #32 completed: a ventilator line and a cardiac theatre line. Other types' fields stay blank."""
    vent = {"type": "equipment", "equipmentType": "ventilator", "quantity": 2}
    room = {"type": "operatingRoom", "capability": "cardiac", "quantity": 1}
    res = create(client_as(Role.DOCTOR), {"severity": "high", "items": [vent, room]})

    assert res.status_code == 201
    assert res.json()["items"] == [vent, room]
    ventilators, theatre = RequestItem.objects.order_by("id")
    assert (ventilators.resource_type, ventilators.equipment_type, ventilators.capability) == (
        "equipment",
        "ventilator",
        "",
    )
    assert (ventilators.blood_group, ventilators.component, ventilators.bed_type) == ("", "", "")
    assert (theatre.resource_type, theatre.capability, theatre.equipment_type) == (
        "operatingRoom",
        "cardiac",
        "",
    )


# ── Access ──────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("role", "read", "write"),
    [
        (Role.ADMIN, 200, 201),
        (Role.DOCTOR, 200, 201),
        (Role.NURSE, 200, 201),
        (Role.BLOOD_BANK, 200, 403),
        (Role.PHARMACIST, 200, 403),
        (Role.PATIENT, 403, 403),
    ],
)
def test_access_by_role(client_as, role, read, write):
    client = client_as(role)
    assert client.get(reverse("emergency-cases")).status_code == read
    assert create(client).status_code == write


def test_signed_out_users_get_nothing(api):
    assert api.get(reverse("emergency-cases")).status_code == 403


def test_staff_see_only_their_own_hospitals_cases(client_as, make_user, make_hospital):
    ours, theirs = make_hospital(name="Ours"), make_hospital(name="Theirs")
    here = client_as(Role.DOCTOR, hospital=ours)
    there = client_as(Role.NURSE, email="nurse@theirs.test", hospital=theirs)
    mine = create(here).json()["id"]
    other = create(there).json()["id"]

    assert [c["id"] for c in here.get(reverse("emergency-cases")).json()] == [mine]
    assert here.get(reverse("emergency-case", args=[mine])).status_code == 200
    assert here.get(reverse("emergency-case", args=[other])).status_code == 404

    admin = client_as(Role.ADMIN)  # no hospital: the whole network; both are critical, so oldest first
    assert [c["id"] for c in admin.get(reverse("emergency-cases")).json()] == [mine, other]


def test_the_list_is_fresh_on_every_request(client_as):
    """Regression: a shared queryset handed back unfiltered cached its rows, so admins saw a frozen list."""
    admin = client_as(Role.ADMIN)
    assert admin.get(reverse("emergency-cases")).json() == []
    create(admin)
    assert len(admin.get(reverse("emergency-cases")).json()) == 1
