"""Story #35: overdue critical cases are escalated by the system, and closing needs an outcome note."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.models import EmergencyRequest, RequestStatusChange
from apps.emergencies.services import OutcomeNoteRequired, apply_case_action, escalate_overdue
from config.settings import positive_int_env

pytestmark = pytest.mark.django_db

SETTING = "EMERGENCY_ESCALATION_MINUTES"
BED = {"type": "bed", "bedType": "icu", "quantity": 1}


@pytest.fixture
def now():
    return timezone.now()


def case_entered(hospital, status, *, reference, minutes_ago, now, severity="critical"):
    """A case that entered `status` `minutes_ago` minutes before `now`. Its latest timeline entry says so."""
    case = EmergencyRequest.objects.create(
        reference=reference, severity=severity, status=status, hospital=hospital
    )
    RequestStatusChange.objects.create(
        request=case,
        from_status="",
        to_status=status,
        action="create",
        at=now - timedelta(minutes=minutes_ago),
    )
    return case


def status_of(case) -> str:
    case.refresh_from_db()
    return case.status


@pytest.mark.parametrize(
    ("status", "severity", "minutes_ago", "expected"),
    [
        ("open", "critical", 45, "escalated"),
        ("matching", "critical", 45, "escalated"),
        ("partiallyFulfilled", "critical", 45, "escalated"),
        ("open", "critical", 10, "open"),  # not yet past the window
        ("open", "critical", 30, "open"),  # exactly the window is not yet overdue: it must be older
        ("open", "high", 45, "open"),
        ("matching", "moderate", 45, "matching"),
        ("open", "low", 45, "open"),
        ("escalated", "critical", 90, "escalated"),  # already escalated: no second one
        ("fulfilled", "critical", 90, "fulfilled"),
        ("closed", "critical", 90, "closed"),
        ("cancelled", "critical", 90, "cancelled"),
    ],
)
def test_only_critical_active_cases_past_the_window_are_escalated(
    make_hospital, now, status, severity, minutes_ago, expected
):
    case = case_entered(
        make_hospital(), status, reference="EC-2026-0001", minutes_ago=minutes_ago, now=now, severity=severity
    )

    with override_settings(EMERGENCY_ESCALATION_MINUTES=30):
        escalate_overdue(now=now)

    assert status_of(case) == expected


def test_an_escalation_is_a_history_entry_with_no_actor_and_its_reason(make_hospital, now):
    case = case_entered(make_hospital(), "matching", reference="EC-2026-0001", minutes_ago=45, now=now)

    assert escalate_overdue(now=now) == 1

    entry = RequestStatusChange.objects.get(request=case, action="escalate")
    assert (entry.from_status, entry.to_status, entry.actor, entry.at) == ("matching", "escalated", None, now)
    assert entry.note == "Not fulfilled within 30 minutes (automatic)"


def test_an_escalation_is_audit_logged_with_no_actor(make_hospital, now):
    case_entered(make_hospital(), "open", reference="EC-2026-0001", minutes_ago=45, now=now)

    escalate_overdue(now=now)

    entry = AuditLog.objects.get(action="emergencyrequest.status_changed")
    assert entry.actor is None and entry.actor_email == ""
    assert entry.before == {"status": "open"} and entry.after == {"status": "escalated"}
    assert entry.reason == "Not fulfilled within 30 minutes (automatic)"


def test_a_case_resumed_to_matching_gets_a_fresh_window(make_hospital, make_user, now):
    hospital = make_hospital()
    doctor = make_user(Role.DOCTOR, hospital=hospital)
    case = case_entered(hospital, "open", reference="EC-2026-0001", minutes_ago=45, now=now)
    assert escalate_overdue(now=now) == 1

    apply_case_action(case.reference, "resumeMatching", note="Blood bank has two units", actor=doctor)

    # Ten minutes after the resume: inside the new window, so it stays matching.
    assert escalate_overdue(now=now + timedelta(minutes=10)) == 0
    assert status_of(case) == "matching"
    # Thirty-one minutes after the resume: past the window, so it is escalated again.
    assert escalate_overdue(now=now + timedelta(minutes=31)) == 1
    assert status_of(case) == "escalated"


def test_a_second_run_escalates_nothing(make_hospital, now):
    case_entered(make_hospital(), "open", reference="EC-2026-0001", minutes_ago=45, now=now)

    assert escalate_overdue(now=now) == 1
    assert escalate_overdue(now=now) == 0
    assert RequestStatusChange.objects.filter(action="escalate").count() == 1


@pytest.mark.parametrize(("setting", "escalated"), [(60, 0), (30, 1), (10, 1)])
def test_the_window_is_the_setting(make_hospital, now, setting, escalated):
    """A case 45 minutes into its status: escalated under a 30- or 10-minute window, not under 60."""
    case_entered(make_hospital(), "open", reference="EC-2026-0001", minutes_ago=45, now=now)

    with override_settings(EMERGENCY_ESCALATION_MINUTES=setting):
        assert escalate_overdue(now=now) == escalated


def test_the_command_escalates_and_prints_the_count(make_hospital):
    case_entered(make_hospital(), "open", reference="EC-2026-0001", minutes_ago=45, now=timezone.now())

    out = StringIO()
    call_command("escalate_overdue_cases", stdout=out)
    assert out.getvalue() == "Escalated 1 overdue case.\n"

    out = StringIO()
    call_command("escalate_overdue_cases", stdout=out)
    assert out.getvalue() == "Escalated 0 overdue cases.\n"


def test_reading_the_list_escalates_first(client_as, make_hospital):
    hospital = make_hospital()
    doctor = client_as(Role.DOCTOR, hospital=hospital)
    case_entered(hospital, "open", reference="EC-2026-0001", minutes_ago=45, now=timezone.now())

    [row] = doctor.get(reverse("emergency-cases")).json()

    assert row["status"] == "escalated"


def test_reading_a_case_escalates_it_first(client_as, make_hospital):
    hospital = make_hospital()
    doctor = client_as(Role.DOCTOR, hospital=hospital)
    case_entered(hospital, "matching", reference="EC-2026-0002", minutes_ago=45, now=timezone.now())

    detail = doctor.get(reverse("emergency-case", args=["EC-2026-0002"])).json()

    assert detail["status"] == "escalated"
    assert [(h["action"], h["actor"]) for h in detail["history"]] == [("create", None), ("escalate", None)]
    assert detail["history"][-1]["note"] == "Not fulfilled within 30 minutes (automatic)"
    assert detail["actions"] == ["resumeMatching", "close"]


def fulfilled_case(hospital, reference="EC-2026-0003"):
    case = EmergencyRequest.objects.create(
        reference=reference, severity="high", status="fulfilled", hospital=hospital
    )
    RequestStatusChange.objects.create(request=case, from_status="", to_status="open", action="create")
    return case


@pytest.mark.parametrize(
    "payload",
    [
        {"action": "close"},
        {"action": "close", "note": ""},
        {"action": "close", "note": "   "},
        {"action": "close", "note": "\n\t "},
    ],
)
def test_closing_without_an_outcome_note_is_400_and_changes_nothing(client_as, make_hospital, payload):
    hospital = make_hospital()
    case = fulfilled_case(hospital)

    res = client_as(Role.DOCTOR, hospital=hospital).post(
        reverse("emergency-case-action", args=[case.reference]), payload, format="json"
    )

    assert res.status_code == 400
    assert res.json() == {"note": ["Add an outcome note to close the case."]}
    assert status_of(case) == "fulfilled"
    assert not RequestStatusChange.objects.filter(action="close").exists()
    assert not AuditLog.objects.filter(reason="close").exists()


def test_closing_with_an_outcome_note_closes_it_and_the_note_is_the_outcome(client_as, make_hospital):
    hospital = make_hospital()
    doctor = client_as(Role.DOCTOR, hospital=hospital)
    case = fulfilled_case(hospital)
    url = reverse("emergency-case-action", args=[case.reference])

    res = doctor.post(
        url, {"action": "close", "note": "  Two units to ward 3; patient stable  "}, format="json"
    )

    assert res.status_code == 200
    assert res.json()["status"] == "closed"
    entry = RequestStatusChange.objects.get(request=case, action="close")
    assert entry.note == "Two units to ward 3; patient stable"
    assert res.json()["outcome"] == "Two units to ward 3; patient stable"
    assert res.json()["actions"] == []


def test_the_outcome_is_null_until_the_case_is_closed(client_as, make_hospital):
    hospital = make_hospital()
    case = fulfilled_case(hospital)

    detail = (
        client_as(Role.DOCTOR, hospital=hospital).get(reverse("emergency-case", args=[case.reference])).json()
    )

    assert detail["outcome"] is None


def test_closing_a_case_that_is_already_closed_says_so_not_that_the_note_is_missing(client_as, make_hospital):
    hospital = make_hospital()
    case = fulfilled_case(hospital)
    doctor = client_as(Role.DOCTOR, hospital=hospital)
    doctor.post(
        reverse("emergency-case-action", args=[case.reference]),
        {"action": "close", "note": "Done"},
        format="json",
    )

    res = doctor.post(
        reverse("emergency-case-action", args=[case.reference]), {"action": "close"}, format="json"
    )

    assert res.status_code == 409
    assert res.json() == {"detail": "Can't close a case that is closed."}


def test_the_service_refuses_a_blank_close_too_not_only_the_api(make_hospital, make_user):
    hospital = make_hospital()
    doctor = make_user(Role.DOCTOR, hospital=hospital)
    case = fulfilled_case(hospital)

    with pytest.raises(OutcomeNoteRequired):
        apply_case_action(case.reference, "close", note="  ", actor=doctor)

    assert status_of(case) == "fulfilled"


@pytest.mark.parametrize("raw", ["1", "30", " 45 "])
def test_the_escalation_setting_reads_a_whole_number_of_one_or_more(monkeypatch, raw):
    monkeypatch.setenv(SETTING, raw)
    assert positive_int_env(SETTING, 30) == int(raw)


def test_the_escalation_setting_defaults_to_thirty_minutes(monkeypatch):
    monkeypatch.delenv(SETTING, raising=False)
    assert positive_int_env(SETTING, 30) == 30


@pytest.mark.parametrize("raw", ["0", "-5", "abc", "", "2.5", "30m"])
def test_a_bad_escalation_setting_refuses_to_start(monkeypatch, raw):
    monkeypatch.setenv(SETTING, raw)
    with pytest.raises(ImproperlyConfigured, match=SETTING):
        positive_int_env(SETTING, 30)
