"""Story #34: a case's status moves along its lifecycle. Each move is in the timeline and the audit log.
A refused move changes nothing."""

import importlib
from datetime import timedelta

import pytest
from django.apps import apps as installed_apps
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.models import REQUEST_LIFECYCLE, EmergencyRequest, RequestStatusChange

pytestmark = pytest.mark.django_db

migration = importlib.import_module("apps.emergencies.migrations.0004_request_status_history")

BED = {"type": "bed", "bedType": "icu", "quantity": 1}

# The agreed lifecycle, written out: (from, action, to). The table in models.py must match it exactly.
ALLOWED = [
    ("open", "startMatching", "matching"),
    ("matching", "partiallyFulfil", "partiallyFulfilled"),
    ("matching", "fulfil", "fulfilled"),
    ("partiallyFulfilled", "fulfil", "fulfilled"),
    ("open", "escalate", "escalated"),
    ("matching", "escalate", "escalated"),
    ("partiallyFulfilled", "escalate", "escalated"),
    ("escalated", "resumeMatching", "matching"),
    ("fulfilled", "close", "closed"),
    ("partiallyFulfilled", "close", "closed"),
    ("escalated", "close", "closed"),
    ("open", "cancel", "cancelled"),
    ("matching", "cancel", "cancelled"),
]

REFUSED = [
    ("open", "close"),
    ("open", "fulfil"),
    ("open", "partiallyFulfil"),
    ("open", "resumeMatching"),
    ("matching", "startMatching"),
    ("matching", "resumeMatching"),
    ("matching", "close"),
    ("partiallyFulfilled", "cancel"),
    ("partiallyFulfilled", "startMatching"),
    ("fulfilled", "cancel"),
    ("fulfilled", "escalate"),
    ("fulfilled", "fulfil"),
    ("escalated", "cancel"),
    ("escalated", "fulfil"),
    ("escalated", "startMatching"),
]


def case_at(hospital, status="open", reference="EC-2026-0001"):
    return EmergencyRequest.objects.create(
        reference=reference, severity="high", status=status, hospital=hospital
    )


def move(client, reference, action, note=None):
    body = {"action": action} if note is None else {"action": action, "note": note}
    return client.post(reverse("emergency-case-action", args=[reference]), body, format="json")


def status_of(case) -> str:
    case.refresh_from_db()
    return case.status


def test_the_lifecycle_is_the_agreed_table():
    assert REQUEST_LIFECYCLE.transitions == {(s, a): e for s, a, e in ALLOWED}


@pytest.mark.parametrize(("start", "action", "end"), ALLOWED)
def test_each_allowed_move_changes_the_status_and_is_recorded(client_as, make_hospital, start, action, end):
    hospital = make_hospital()
    case = case_at(hospital, start)

    res = move(client_as(Role.DOCTOR, hospital=hospital), case.reference, action, note="Two units on hold")

    assert res.status_code == 200
    assert res.json()["status"] == end
    assert status_of(case) == end
    [entry] = RequestStatusChange.objects.filter(request=case)
    assert (entry.from_status, entry.to_status, entry.action, entry.note) == (
        start,
        end,
        action,
        "Two units on hold",
    )
    assert entry.actor.email == "doctor@example.com"


@pytest.mark.parametrize(("start", "action"), REFUSED)
def test_a_refused_move_is_409_and_changes_nothing(client_as, make_hospital, start, action):
    hospital = make_hospital()
    case = case_at(hospital, start)

    res = move(client_as(Role.DOCTOR, hospital=hospital), case.reference, action, note="Trying anyway")

    assert res.status_code == 409
    assert status_of(case) == start
    assert not RequestStatusChange.objects.exists()
    assert not AuditLog.objects.filter(action="emergencyrequest.status_changed").exists()


def test_a_refused_move_says_why(client_as, make_hospital):
    hospital = make_hospital()
    case = case_at(hospital, "open")
    res = move(client_as(Role.DOCTOR, hospital=hospital), case.reference, "close")
    assert res.json() == {"detail": "Can't close a case that is open."}


@pytest.mark.parametrize("start", ["closed", "cancelled"])
@pytest.mark.parametrize("action", REQUEST_LIFECYCLE.actions)
def test_closed_and_cancelled_cases_refuse_every_move(client_as, make_hospital, start, action):
    hospital = make_hospital()
    case = case_at(hospital, start)

    res = move(client_as(Role.ADMIN, hospital=hospital), case.reference, action)

    assert res.status_code == 409
    assert status_of(case) == start


def test_an_unknown_action_is_400(client_as, make_hospital):
    hospital = make_hospital()
    case = case_at(hospital)
    res = move(client_as(Role.DOCTOR, hospital=hospital), case.reference, "explode")
    assert res.status_code == 400 and "action" in res.json()
    assert status_of(case) == "open"


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_view_only_roles_cannot_move_a_case(client_as, make_hospital, role):
    hospital = make_hospital()
    case = case_at(hospital)
    res = move(client_as(role, hospital=hospital), case.reference, "startMatching")
    assert res.status_code == 403
    assert status_of(case) == "open"


def test_another_hospitals_case_is_404_and_untouched(client_as, make_hospital):
    ours, theirs = make_hospital(name="Ours"), make_hospital(name="Theirs")
    case = case_at(theirs)

    res = move(client_as(Role.DOCTOR, hospital=ours), case.reference, "startMatching")

    assert res.status_code == 404
    assert status_of(case) == "open"
    assert not RequestStatusChange.objects.exists()


def test_staff_without_a_hospital_get_404_on_a_hospitals_case(client_as, make_hospital):
    case = case_at(make_hospital())
    res = move(client_as(Role.NURSE), case.reference, "startMatching")
    assert res.status_code == 404
    assert status_of(case) == "open"


def test_an_unknown_reference_is_404(client_as):
    res = move(client_as(Role.DOCTOR), "EC-2026-9999", "startMatching")
    assert res.status_code == 404


def test_admins_can_move_a_case_at_any_hospital(client_as, make_hospital):
    case = case_at(make_hospital(name="Ours"))
    admin = client_as(Role.ADMIN, hospital=make_hospital(name="Elsewhere"))

    res = move(admin, case.reference, "startMatching")

    assert res.status_code == 200 and res.json()["status"] == "matching"


def test_opening_a_case_starts_its_timeline(client_as):
    doctor = client_as(Role.DOCTOR)
    reference = doctor.post(
        reverse("emergency-cases"), {"severity": "high", "items": [BED]}, format="json"
    ).json()["id"]

    [entry] = RequestStatusChange.objects.all()
    assert entry.request.reference == reference
    assert (entry.from_status, entry.to_status, entry.action, entry.note) == ("", "open", "create", "")
    assert entry.actor.email == "doctor@example.com"


def test_a_move_is_audit_logged_with_actor_statuses_and_note(client_as, make_hospital):
    hospital = make_hospital()
    case = case_at(hospital)

    move(
        client_as(Role.NURSE, hospital=hospital),
        case.reference,
        "startMatching",
        note="Blood bank called back",
    )

    entry = AuditLog.objects.get(action="emergencyrequest.status_changed")
    assert entry.actor_email == "nurse@example.com"
    assert entry.target_repr == case.reference
    assert entry.before == {"status": "open"} and entry.after == {"status": "matching"}
    assert entry.reason == "Blood bank called back"


def test_a_move_without_a_note_is_audited_under_its_action(client_as, make_hospital):
    hospital = make_hospital()
    case = case_at(hospital)

    move(client_as(Role.DOCTOR, hospital=hospital), case.reference, "escalate")

    assert AuditLog.objects.get(action="emergencyrequest.status_changed").reason == "escalate"
    assert RequestStatusChange.objects.get().note == ""


def test_a_note_over_500_characters_is_refused(client_as, make_hospital):
    hospital = make_hospital()
    case = case_at(hospital)

    res = move(client_as(Role.DOCTOR, hospital=hospital), case.reference, "startMatching", note="x" * 501)

    assert res.status_code == 400 and "note" in res.json()
    assert status_of(case) == "open"
    assert not RequestStatusChange.objects.exists()


def test_a_note_of_exactly_500_characters_is_kept(client_as, make_hospital):
    hospital = make_hospital()
    case = case_at(hospital)

    res = move(client_as(Role.DOCTOR, hospital=hospital), case.reference, "startMatching", note="x" * 500)

    assert res.status_code == 200
    assert RequestStatusChange.objects.get().note == "x" * 500


def test_the_case_page_gets_its_timeline_in_order_and_the_moves_valid_now(client_as, make_hospital):
    hospital = make_hospital()
    doctor = client_as(Role.DOCTOR, hospital=hospital, first_name="Ayesha", last_name="Khan")
    reference = doctor.post(
        reverse("emergency-cases"), {"severity": "critical", "items": [BED]}, format="json"
    ).json()["id"]
    move(doctor, reference, "startMatching", note="First call")
    move(doctor, reference, "partiallyFulfil", note="Two of four")

    detail = doctor.get(reverse("emergency-case", args=[reference])).json()

    assert [(h["fromStatus"], h["toStatus"], h["action"], h["note"]) for h in detail["history"]] == [
        ("", "open", "create", ""),
        ("open", "matching", "startMatching", "First call"),
        ("matching", "partiallyFulfilled", "partiallyFulfil", "Two of four"),
    ]
    assert [h["actor"] for h in detail["history"]] == ["Ayesha Khan"] * 3
    assert detail["actions"] == ["fulfil", "escalate", "close"]


def test_a_terminal_case_offers_no_moves(client_as, make_hospital):
    hospital = make_hospital()
    case = case_at(hospital, "cancelled")
    detail = (
        client_as(Role.DOCTOR, hospital=hospital).get(reverse("emergency-case", args=[case.reference])).json()
    )
    assert detail["actions"] == []


def test_the_list_leaves_out_the_timeline_and_the_moves(client_as, make_hospital):
    hospital = make_hospital()
    case_at(hospital)
    [row] = client_as(Role.DOCTOR, hospital=hospital).get(reverse("emergency-cases")).json()
    assert "history" not in row and "actions" not in row


def test_the_backfill_gives_each_existing_case_a_creation_entry(make_user, make_hospital):
    hospital = make_hospital()
    actor = make_user(Role.DOCTOR, hospital=hospital)
    opened = timezone.now() - timedelta(days=2)
    case = EmergencyRequest.objects.create(
        reference="EC-2026-0001", severity="high", hospital=hospital, created_by=actor
    )
    EmergencyRequest.objects.filter(pk=case.pk).update(created_at=opened)
    orphan = EmergencyRequest.objects.create(
        reference="EC-2026-0002", severity="low"
    )  # its creator was removed

    migration.backfill_created(installed_apps, None)

    entry = RequestStatusChange.objects.get(request=case)
    assert (entry.from_status, entry.to_status, entry.action, entry.at) == ("", "open", "create", opened)
    assert entry.actor_id == actor.pk
    assert RequestStatusChange.objects.get(request=orphan).actor_id is None
