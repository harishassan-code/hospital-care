"""Story #52 in the API: the list (newest first, 50 at most, `unread`), the unread count, and mark read. Each
person sees only their own rows. Signed out and patients get 403; another person's row is 404."""

from datetime import timedelta

import pytest
from django.contrib import admin
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.matching.tests.reservation_support import staff
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db

KEYS = {"id", "kind", "severity", "message", "link", "createdAt", "readAt"}


@pytest.fixture
def me(make_user, make_hospital):
    return staff(make_user, make_hospital(), Role.NURSE)


@pytest.fixture
def api_as(me):
    client = APIClient()
    client.force_authenticate(me)
    return client


def make_row(user, *, minutes_ago=0, read=False, kind="case.created", message="A case is open."):
    row = Notification.objects.create(
        user=user,
        kind=kind,
        severity="critical" if kind == "case.created" else "info",
        message=message,
        link="/staff/emergencies/EC-2026-0001",
        created_at=timezone.now() - timedelta(minutes=minutes_ago),
        read_at=timezone.now() if read else None,
    )
    return row


def test_the_list_is_the_users_own_rows_newest_first_in_the_camel_case_shape(api_as, me, make_user):
    old = make_row(me, minutes_ago=30)
    new = make_row(me, minutes_ago=1, kind="transfer.requested", message="Transfer asked.")
    make_row(make_user(Role.NURSE, email="other@example.com"), minutes_ago=0)

    response = api_as.get(reverse("notification-list"))

    assert response.status_code == 200
    assert [row["id"] for row in response.json()] == [new.pk, old.pk]
    assert set(response.json()[0]) == KEYS
    assert response.json()[0]["readAt"] is None
    assert response.json()[0]["severity"] == "info"


def test_the_list_is_capped_at_fifty_newest(api_as, me):
    for minutes in range(55):
        make_row(me, minutes_ago=minutes)
    rows = api_as.get(reverse("notification-list")).json()
    assert len(rows) == 50
    assert rows[0]["createdAt"] > rows[-1]["createdAt"]


@pytest.mark.parametrize("flag", ["true", "1"])
def test_unread_true_keeps_only_the_unread(api_as, me, flag):
    unread = make_row(me, minutes_ago=2)
    make_row(me, minutes_ago=1, read=True)
    rows = api_as.get(reverse("notification-list"), {"unread": flag}).json()
    assert [row["id"] for row in rows] == [unread.pk]


def test_unread_false_and_no_flag_keep_everything(api_as, me):
    make_row(me, read=True)
    make_row(me)
    assert len(api_as.get(reverse("notification-list"), {"unread": "false"}).json()) == 2
    assert len(api_as.get(reverse("notification-list")).json()) == 2


def test_a_value_that_is_not_a_boolean_is_400(api_as):
    assert api_as.get(reverse("notification-list"), {"unread": "maybe"}).status_code == 400


def test_the_unread_count_counts_only_the_users_unread_rows(api_as, me, make_user):
    make_row(me)
    make_row(me)
    make_row(me, read=True)
    make_row(make_user(Role.NURSE, email="other@example.com"))

    response = api_as.get(reverse("notification-unread-count"))

    assert response.status_code == 200
    assert response.json() == {"count": 2}


def test_marking_read_sets_read_at_and_returns_the_row(api_as, me):
    row = make_row(me)

    response = api_as.post(reverse("notification-read", args=[row.pk]))

    assert response.status_code == 200
    assert set(response.json()) == KEYS
    assert response.json()["readAt"] is not None
    assert api_as.get(reverse("notification-unread-count")).json() == {"count": 0}


def test_a_second_mark_keeps_the_first_time_and_writes_no_second_audit_row(api_as, me):
    row = make_row(me)
    first = api_as.post(reverse("notification-read", args=[row.pk])).json()["readAt"]

    second = api_as.post(reverse("notification-read", args=[row.pk]))

    assert second.status_code == 200
    assert second.json()["readAt"] == first
    audit = AuditLog.objects.filter(action="notification.read", target_id=str(row.pk))
    assert audit.count() == 1
    assert audit.get().target_type == "notifications.notification"
    assert audit.get().actor_email == me.email


def test_another_persons_row_is_404_and_stays_unread(api_as, make_user):
    theirs = make_row(make_user(Role.DOCTOR, email="doctor@example.com"))

    response = api_as.post(reverse("notification-read", args=[theirs.pk]))

    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.read_at is None
    assert not AuditLog.objects.filter(action="notification.read").exists()


def test_an_unknown_row_is_404(api_as):
    assert api_as.post(reverse("notification-read", args=[999999])).status_code == 404


@pytest.mark.parametrize(
    ("method", "name", "args"),
    [
        ("get", "notification-list", []),
        ("get", "notification-unread-count", []),
        ("post", "notification-read", [1]),
    ],
)
def test_signed_out_is_403(method, name, args):
    response = getattr(APIClient(), method)(reverse(name, args=args))
    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "name", "args"),
    [
        ("get", "notification-list", []),
        ("get", "notification-unread-count", []),
        ("post", "notification-read", [1]),
    ],
)
def test_a_patient_is_403(client_as, method, name, args):
    response = getattr(client_as(Role.PATIENT), method)(reverse(name, args=args))
    assert response.status_code == 403


def test_an_admin_without_a_hospital_gets_an_empty_list(client_as):
    client = client_as(Role.ADMIN)
    assert client.get(reverse("notification-list")).json() == []
    assert client.get(reverse("notification-unread-count")).json() == {"count": 0}


def test_the_admin_site_is_read_only_for_notifications():
    model_admin = admin.site._registry[Notification]
    assert not model_admin.has_add_permission(None)
    assert not model_admin.has_change_permission(None)
    assert not model_admin.has_delete_permission(None)
