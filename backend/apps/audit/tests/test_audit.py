"""Story 8.1 Action logging: one-call helper, full entries, append-only."""

import pytest
from django.contrib.admin.sites import site
from django.test import RequestFactory
from django.urls import Resolver404, resolve

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.audit.services import record

pytestmark = pytest.mark.django_db


@pytest.fixture
def entry(make_user):
    nurse = make_user(Role.NURSE, first_name="Hina", last_name="Javed")
    return record(
        make_user(Role.ADMIN),
        "user.role_changed",
        nurse,
        before={"role": "nurse"},
        after={"role": "doctor"},
        reason="Moved to the medical team",
    )


def test_one_call_stores_actor_action_target_values_and_time(entry):
    entry = AuditLog.objects.get(pk=entry.pk)
    assert entry.actor_email == "admin@example.com" and entry.actor.role == Role.ADMIN
    assert (entry.action, entry.target_type, entry.target_repr) == (
        "user.role_changed",
        "accounts.user",
        "nurse@example.com",
    )
    assert (entry.before, entry.after, entry.reason) == (
        {"role": "nurse"},
        {"role": "doctor"},
        "Moved to the medical team",
    )
    assert entry.at is not None


def test_the_system_can_act_without_a_user(make_user):
    entry = record(None, "user.created", make_user(Role.PATIENT))
    assert entry.actor is None and entry.actor_email == ""


def test_entries_cannot_be_edited_or_deleted(entry):
    entry.action = "nothing.happened"
    with pytest.raises(PermissionError):
        entry.save()
    with pytest.raises(PermissionError):
        entry.delete()
    with pytest.raises(PermissionError):
        AuditLog.objects.all().update(action="x")
    with pytest.raises(PermissionError):
        AuditLog.objects.all().delete()
    assert AuditLog.objects.get().action == "user.role_changed"


def test_the_actors_email_survives_their_account(entry):
    entry.actor.delete()  # Django sets actor to NULL through the base manager, which allows it
    entry = AuditLog.objects.get()
    assert entry.actor is None and entry.actor_email == "admin@example.com"


def test_there_is_no_api_to_change_entries():
    with pytest.raises(Resolver404):
        resolve("/api/audit/")


def test_admin_is_read_only(make_user):
    request = RequestFactory().get("/")
    request.user = make_user(Role.ADMIN, is_superuser=True, is_staff=True)
    admin = site._registry[AuditLog]
    assert not admin.has_add_permission(request)
    assert not admin.has_change_permission(request)
    assert not admin.has_delete_permission(request)
