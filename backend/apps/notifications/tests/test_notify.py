"""Story #52 at the service: `notify` picks the people (active, at the hospital, a role with edit on the
module, never the actor), writes one row each, hands each row to every channel, and writes no audit record."""

import pytest

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.matching.tests.reservation_support import staff
from apps.notifications import services
from apps.notifications.channels import Channel
from apps.notifications.models import Notification, Severity
from apps.notifications.services import notify

pytestmark = pytest.mark.django_db


@pytest.fixture
def ward(make_user, make_hospital):
    """CityCare General's staff, one of each role, and a doctor at another hospital."""
    here = make_hospital(name="CityCare General")
    there = make_hospital(name="Seaview")
    return {
        "here": here,
        "doctor": staff(make_user, here, Role.DOCTOR),
        "nurse": staff(make_user, here, Role.NURSE),
        "admin": staff(make_user, here, Role.ADMIN),
        "blood_bank": staff(make_user, here, Role.BLOOD_BANK),
        "pharmacist": staff(make_user, here, Role.PHARMACIST),
        "patient": staff(make_user, here, Role.PATIENT),
        "other_doctor": staff(make_user, there, Role.DOCTOR),
    }


def recipients_of(rows) -> set[int]:
    return {row.user_id for row in rows}


def test_the_recipients_are_the_hospitals_staff_whose_role_can_edit_the_module(ward):
    emergencies = notify(
        "case.created",
        hospital=ward["here"],
        module="emergencies",
        message="m",
        link="/",
        severity="critical",
    )
    blood = notify("transfer.requested", hospital=ward["here"], module="blood", message="m", link="/")
    equipment = notify("transfer.requested", hospital=ward["here"], module="equipment", message="m", link="/")

    assert recipients_of(emergencies) == {ward[k].pk for k in ("doctor", "nurse", "admin")}
    assert recipients_of(blood) == {ward[k].pk for k in ("admin", "blood_bank")}
    assert recipients_of(equipment) == {ward[k].pk for k in ("admin", "nurse")}


def test_a_superuser_counts_as_an_admin(ward, make_user):
    boss = make_user(Role.PATIENT, email="boss@example.com", hospital=ward["here"], is_superuser=True)
    rows = notify("case.created", hospital=ward["here"], module="emergencies", message="m", link="/")
    assert boss.pk in recipients_of(rows)


def test_the_actor_is_left_out(ward):
    rows = notify(
        "case.created",
        hospital=ward["here"],
        module="emergencies",
        message="m",
        link="/",
        actor=ward["doctor"],
    )
    assert ward["doctor"].pk not in recipients_of(rows)
    assert ward["nurse"].pk in recipients_of(rows)


def test_inactive_users_and_other_hospitals_get_nothing(ward):
    ward["nurse"].is_active = False
    ward["nurse"].save(update_fields=["is_active"])
    rows = notify("case.created", hospital=ward["here"], module="emergencies", message="m", link="/")
    assert recipients_of(rows) == {ward["doctor"].pk, ward["admin"].pk}


def test_no_hospital_means_no_rows(ward):
    assert notify("case.created", hospital=None, module="emergencies", message="m", link="/") == []
    assert Notification.objects.count() == 0


def test_a_row_carries_the_event_and_nothing_is_audit_logged(ward):
    rows = notify(
        "case.escalated",
        hospital=ward["here"],
        module="emergencies",
        severity=Severity.CRITICAL,
        message="Case EC-2026-0001 is escalated.",
        link="/staff/emergencies/EC-2026-0001",
    )
    row = Notification.objects.get(pk=rows[0].pk)
    assert (row.kind, row.severity, row.link, row.read_at) == (
        "case.escalated",
        "critical",
        "/staff/emergencies/EC-2026-0001",
        None,
    )
    assert AuditLog.objects.filter(target_type="notifications.notification").count() == 0


def test_a_long_message_is_cut_to_the_stored_length(ward):
    notify("case.created", hospital=ward["here"], module="emergencies", message="x" * 400, link="/")
    assert {len(message) for message in Notification.objects.values_list("message", flat=True)} == {300}


def test_each_new_row_is_handed_to_every_channel(ward, monkeypatch):
    seen = []

    class Recorder(Channel):
        def send(self, notification):
            seen.append(notification.pk)

    monkeypatch.setattr(services, "CHANNELS", [Recorder(), Recorder()])
    rows = notify("case.created", hospital=ward["here"], module="emergencies", message="m", link="/")
    assert sorted(seen) == sorted([row.pk for row in rows] * 2)
