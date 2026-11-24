"""Patient privacy (B23): the minimum necessary, a record of who saw patient details, and nothing identifying
in the wrong places. docs/testing/privacy-review.md lists each safeguard and the test that holds it."""

from datetime import timedelta

import pytest
from django.core.cache import cache
from django.urls import URLPattern, URLResolver, get_resolver, reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.models import PatientTransfer
from apps.emergencies.services import create_case
from apps.hospitals.models import Bed, BedStatus, Ward
from apps.notifications.models import Notification
from apps.operating_rooms.models import OperatingRoom, OrBooking

pytestmark = pytest.mark.django_db

REF = "PRIV-REF-9431"  # a patient reference no response may carry to the wrong people
INITIALS = "Q.Z."


@pytest.fixture
def world(make_hospital, make_user):
    home, other = make_hospital(), make_hospital(name="Seaview Hospital")
    ward = Ward.objects.create(code="medA", hospital=home, name="Medical A", kind="General medicine")
    Bed.objects.create(
        label="MA-01",
        ward=ward,
        status=BedStatus.OCCUPIED,
        patient_initials=INITIALS,
        patient_age=50,
        patient_sex="F",
    )
    room = OperatingRoom.objects.create(hospital=home, name="OR 1", capabilities=["general"])
    start = timezone.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    nurse = make_user(Role.NURSE, email="nurse@home.example", hospital=home)
    OrBooking.objects.create(
        room=room,
        booked_by=nurse,
        starts_at=start,
        ends_at=start + timedelta(hours=1),
        procedure="Hernia repair",
        patient_initials=INITIALS,
    )
    case = create_case(
        severity="critical",
        patient_ref=REF,
        items=[{"type": "blood", "group": "O-", "component": "redCells", "quantity": 2}],
        actor=nurse,
    )
    return {"home": home, "other": other, "case": case, "nurse": nurse}


def text(response) -> str:
    if getattr(response, "streaming", False):  # an export
        return b"".join(response.streaming_content).decode()
    return response.content.decode()


# ── Minimum necessary, role by role ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("role", "at_home", "sees"),
    [
        (Role.NURSE, True, True),
        (Role.DOCTOR, True, True),
        (Role.ADMIN, True, True),  # the admin who runs this hospital
        (Role.ADMIN, False, False),  # the CityCare admin: counts and statuses only
    ],
)
def test_bed_occupants_only_for_clinical_staff_and_the_hospitals_admin(client_as, world, role, at_home, sees):
    extra = {"hospital": world["home"]} if at_home else {}
    body = client_as(role, email=f"{role}-{at_home}@example.com", **extra).get(reverse("bed-board"))
    assert (INITIALS in text(body)) is sees
    assert body.json()["beds"][0]["status"] == "occupied"  # the status is always there


@pytest.mark.parametrize(
    ("role", "at_home", "sees"),
    [
        (Role.NURSE, True, True),
        (Role.BLOOD_BANK, True, False),  # works from the needs, not the patient
        (Role.PHARMACIST, True, False),
        (Role.ADMIN, False, False),
    ],
)
def test_a_cases_patient_reference_follows_the_rule(client_as, world, role, at_home, sees):
    extra = {"hospital": world["home"]} if at_home else {}
    client = client_as(role, email=f"{role}-{at_home}@example.com", **extra)
    listed = client.get(reverse("emergency-cases")).json()
    assert [c["patientRef"] for c in listed] == ([REF] if sees else [None])
    detail = client.get(reverse("emergency-case", args=[world["case"].reference])).json()
    assert (detail["patientRef"] == REF) is sees


def test_a_hospital_admin_never_sees_another_hospitals_patients(client_as, world):
    other_admin = client_as(Role.ADMIN, email="admin@seaview.example", hospital=world["other"])
    assert INITIALS not in text(other_admin.get(reverse("bed-board")))
    assert REF not in text(other_admin.get(reverse("emergency-cases")))


def test_theatre_bookings_show_initials_only_at_home(client_as, world):
    day = timezone.localdate().isoformat()
    url = reverse("operating-room-schedule")
    home = client_as(Role.NURSE, email="n2@example.com", hospital=world["home"]).get(url, {"date": day})
    network = client_as(Role.ADMIN, email="network@example.com").get(url, {"date": day})
    assert INITIALS in text(home)
    assert INITIALS not in text(network)


def test_the_receiving_hospital_learns_who_is_coming_only_once_the_move_is_asked(client_as, world, make_user):
    doctor = make_user(Role.DOCTOR, email="dr@seaview.example", hospital=world["other"])
    case = world["case"]
    assert not PatientTransfer.objects.exists()
    PatientTransfer.objects.create(
        request=case, from_hospital=world["home"], to_hospital=world["other"], requested_by=world["nurse"]
    )
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(doctor)
    [row] = client.get(reverse("patient-transfer-list"), {"direction": "incoming"}).json()
    assert row["patientRef"] == REF


# ── A record of access ─────────────────────────────────────────────────────────────────────────────


def test_each_look_at_patient_details_is_recorded_once_per_ten_minutes(client_as, world):
    cache.clear()
    nurse = client_as(Role.NURSE, email="n3@example.com", hospital=world["home"])
    for _ in range(3):  # the page's 30-second refresh
        nurse.get(reverse("bed-board"))
    views = AuditLog.objects.filter(action="phi.view")
    assert views.count() == 1
    assert views.get().after == {"view": "beds", "hospital": world["home"].name, "records": 1}
    nurse.get(reverse("emergency-case", args=[world["case"].reference]))
    assert views.count() == 2  # another record is another view
    entries = client_as(Role.ADMIN, email="a@example.com", hospital=world["home"]).get(
        reverse("audit-entry-list"), {"action": "phi.view"}
    )
    assert entries.json()["count"] == 2  # admins can filter by it


def test_no_record_when_no_patient_details_were_shown(client_as, world):
    cache.clear()
    client_as(Role.BLOOD_BANK, email="b@example.com", hospital=world["home"]).get(reverse("emergency-cases"))
    client_as(Role.ADMIN, email="network@example.com").get(reverse("bed-board"))
    assert not AuditLog.objects.filter(action="phi.view").exists()


# ── Nothing identifying in the wrong places ────────────────────────────────────────────────────────


def test_notifications_carry_references_and_tags_never_patient_details(world, make_user):
    make_user(Role.NURSE, email="n4@example.com", hospital=world["home"])  # someone to notify
    from apps.emergencies.services import apply_case_action

    apply_case_action(
        world["case"].reference, "escalate", note=f"Patient {REF} {INITIALS}", actor=world["nurse"]
    )
    messages = list(Notification.objects.values_list("message", flat=True))
    assert messages
    for message in messages:
        assert REF not in message and INITIALS not in message


def api_list_routes():
    """Every API route that takes no id: lists and pages a role can open."""

    def walk(patterns, prefix=""):
        for p in patterns:
            route = prefix + str(p.pattern)
            if isinstance(p, URLResolver):
                yield from walk(p.url_patterns, route)
            elif isinstance(p, URLPattern) and route.startswith("api/") and "<" not in route:
                yield "/" + route

    return sorted(set(walk(get_resolver().url_patterns)))


@pytest.mark.parametrize(
    ("role", "at_home"),
    [
        (Role.BLOOD_BANK, True),
        (Role.PHARMACIST, True),
        (Role.ADMIN, False),
        (Role.ADMIN, "other"),
        (None, False),
    ],
)
def test_no_list_in_the_api_leaks_a_patient_to_a_role_outside_the_rules(client_as, world, role, at_home):
    """The coverage check (#114, extended in B23): every list endpoint, read by every role that may not see
    patient details, carries neither the case's patient reference nor the occupant's initials. A new endpoint
    that returns patient fields to the wrong role fails here."""
    from rest_framework.test import APIClient

    if role is None:
        client = APIClient()
    else:
        hospital = world["home"] if at_home is True else world["other"] if at_home == "other" else None
        client = client_as(role, email=f"sweep-{role}-{at_home}@example.com", hospital=hospital)
    day = timezone.localdate().isoformat()
    for route in api_list_routes():
        response = client.get(route, {"date": day, "metrics": "er.arrivals"})
        if response.status_code != 200 or not response.get("Content-Type", "").startswith(
            ("application/json", "text/")
        ):
            continue
        body = text(response)
        assert REF not in body, f"{route} shows the patient reference to {role}"
        assert INITIALS not in body, f"{route} shows the occupant to {role}"


def test_the_audit_log_hides_another_hospitals_case_notes(client_as, world):
    from apps.emergencies.services import apply_case_action

    apply_case_action(
        world["case"].reference, "escalate", note=f"Patient {REF} is deteriorating", actor=world["nurse"]
    )
    url = reverse("audit-entry-list")
    query = {"action": "emergencyrequest.status_changed"}
    own = client_as(Role.ADMIN, email="admin@home.example", hospital=world["home"]).get(url, query)
    other = client_as(Role.ADMIN, email="admin@seaview.example", hospital=world["other"]).get(url, query)
    network = client_as(Role.ADMIN, email="network@example.com").get(url, query)
    assert REF in text(own)
    assert REF not in text(other) and "(hidden: patient information)" in text(other)
    assert REF not in text(network)
    export = client_as(Role.ADMIN, email="admin2@seaview.example", hospital=world["other"]).get(
        reverse("audit-entry-export"), query
    )
    assert REF not in text(export)


def test_blood_bank_reads_the_systems_notes_but_not_the_nurses(client_as, world):
    from apps.emergencies.models import RequestStatusChange

    case = world["case"]
    RequestStatusChange.objects.create(
        request=case,
        from_status="open",
        to_status="open",
        action="note",
        note=f"Patient {REF}",
        actor=world["nurse"],
    )
    RequestStatusChange.objects.create(
        request=case,
        from_status="open",
        to_status="open",
        action="note",
        note="Every need allocated",
        actor=None,
    )
    bank = client_as(Role.BLOOD_BANK, email="bank@home.example", hospital=world["home"])
    notes = [e["note"] for e in bank.get(reverse("emergency-case", args=[case.reference])).json()["history"]]
    assert "Every need allocated" in notes and not any(REF in n for n in notes)
