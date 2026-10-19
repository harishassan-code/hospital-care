"""Story 1.2 Role management: admins see and change roles; every change is audit-logged."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.audit.models import AuditLog
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(make_user):
    return make_user(Role.ADMIN, first_name="Amna", last_name="Admin")


@pytest.fixture
def admin_client(admin):
    client = APIClient()
    client.force_authenticate(admin)
    return client


def change(client, user_id, role):
    return client.patch(reverse("user-role", args=[user_id]), {"role": role}, format="json")


def test_roles_are_defined_in_the_schema():
    """Roles live in a migrated choice list (accounts 0002), so every database has them without seeding."""
    assert [r.value for r in Role] == ["admin", "doctor", "nurse", "bloodBank", "pharmacist", "patient"]


def test_admin_lists_users_with_role_and_hospital(admin_client, admin, make_user, make_hospital):
    hospital = make_hospital()
    make_user(Role.NURSE, first_name="Hina", last_name="Javed", hospital=hospital)
    rows = {row["email"]: row for row in admin_client.get(reverse("user-list")).json()}
    assert rows["nurse@example.com"] == {
        "id": rows["nurse@example.com"]["id"],
        "email": "nurse@example.com",
        "fullName": "Hina Javed",
        "role": "nurse",
        "hospital": {"id": hospital.pk, "name": hospital.name},
        "isActive": True,
        "roleLocked": False,
    }
    assert rows["admin@example.com"]["roleLocked"] is True  # your own account


def test_admin_changes_a_role_and_it_is_audit_logged(admin_client, admin, make_user):
    nurse = make_user(Role.NURSE)
    response = change(admin_client, nurse.pk, Role.DOCTOR)
    assert response.status_code == 200 and response.json()["role"] == "doctor"
    nurse.refresh_from_db()
    assert nurse.role == Role.DOCTOR
    entry = AuditLog.objects.get(action="user.role_changed")
    assert (entry.actor, entry.actor_email) == (admin, admin.email)
    assert (entry.target_type, entry.target_id) == ("accounts.user", str(nurse.pk))
    assert (entry.before, entry.after) == ({"role": "nurse"}, {"role": "doctor"})


def test_the_new_role_applies_on_the_users_next_request(admin_client, make_user, api):
    make_user(Role.NURSE, email="hina@example.com")
    api.get(reverse("auth-csrf"))
    api.post(
        reverse("auth-login"),
        {"email": "hina@example.com", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=api.cookies["csrftoken"].value,
    )
    assert api.get(reverse("blood-units")).status_code == 403
    change(admin_client, User.objects.get(email="hina@example.com").pk, Role.BLOOD_BANK)
    assert api.get(reverse("auth-me")).json()["role"] == "bloodBank"
    assert api.get(reverse("blood-units")).status_code == 200


def test_unchanged_role_writes_no_audit_entry(admin_client, make_user):
    nurse = make_user(Role.NURSE)
    assert change(admin_client, nurse.pk, Role.NURSE).status_code == 200
    assert not AuditLog.objects.exists()


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ("self", "You can't change your own role."),
        ("superuser", "This account is a superuser. Change it in Django admin."),
    ],
)
def test_locked_accounts_are_refused(admin_client, admin, make_user, target, message):
    user = admin if target == "self" else make_user(Role.DOCTOR, email="root@example.com", is_superuser=True)
    response = change(admin_client, user.pk, Role.PATIENT)
    assert response.status_code == 400 and response.json() == {"role": [message]}
    user.refresh_from_db()
    assert user.effective_role in (Role.ADMIN, Role.DOCTOR) and not AuditLog.objects.exists()


def test_unknown_role_and_unknown_user(admin_client, make_user):
    nurse = make_user(Role.NURSE)
    assert change(admin_client, nurse.pk, "surgeon").status_code == 400
    assert change(admin_client, 999_999, Role.DOCTOR).status_code == 404


def test_me_reports_the_users_hospital(client_as, make_hospital):
    hospital = make_hospital()
    me = client_as(Role.NURSE, hospital=hospital).get(reverse("auth-me")).json()
    assert me["hospital"] == {"id": hospital.pk, "name": hospital.name}
    assert client_as(Role.PATIENT).get(reverse("auth-me")).json()["hospital"] is None
