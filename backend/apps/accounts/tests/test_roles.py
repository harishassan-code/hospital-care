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


def test_admin_changes_a_role_and_it_is_audit_logged(admin_client, admin, make_user, make_hospital):
    nurse = make_user(Role.NURSE, hospital=make_hospital())
    response = change(admin_client, nurse.pk, Role.DOCTOR)
    assert response.status_code == 200 and response.json()["role"] == "doctor"
    nurse.refresh_from_db()
    assert nurse.role == Role.DOCTOR
    entry = AuditLog.objects.get(action="user.role_changed")
    assert (entry.actor, entry.actor_email) == (admin, admin.email)
    assert (entry.target_type, entry.target_id) == ("accounts.user", str(nurse.pk))
    assert (entry.before, entry.after) == ({"role": "nurse"}, {"role": "doctor"})


def test_the_new_role_applies_on_the_users_next_request(admin_client, make_user, make_hospital, api):
    make_user(Role.NURSE, email="hina@example.com", hospital=make_hospital())
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


def test_unchanged_role_writes_no_audit_entry(admin_client, make_user, make_hospital):
    nurse = make_user(Role.NURSE, hospital=make_hospital())
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


# Functional sweep, F12: a role that works at one hospital needs one; the admin sets it in the same change.


def assign(client, user_id, role, hospital_id):
    body = {"role": role, "hospitalId": hospital_id}
    return client.patch(reverse("user-role", args=[user_id]), body, format="json")


def test_a_hospital_role_without_a_hospital_is_refused(admin_client, make_user):
    patient = make_user(Role.PATIENT, email="new@example.com")
    response = change(admin_client, patient.pk, Role.NURSE)
    assert response.status_code == 400
    assert response.json() == {"hospitalId": ["Choose the hospital this person works at."]}
    patient.refresh_from_db()
    assert patient.role == Role.PATIENT and not AuditLog.objects.exists()


def test_promoting_a_patient_sets_role_and_hospital_and_logs_both(admin_client, make_user, make_hospital):
    hospital = make_hospital(name="Seaview Hospital")
    patient = make_user(Role.PATIENT, email="new@example.com")
    response = assign(admin_client, patient.pk, Role.NURSE, hospital.pk)
    assert response.status_code == 200
    assert response.json()["role"] == "nurse"
    assert response.json()["hospital"] == {"id": hospital.pk, "name": "Seaview Hospital"}
    patient.refresh_from_db()
    assert (patient.role, patient.hospital) == (Role.NURSE, hospital)
    entry = AuditLog.objects.get(action="user.role_changed")
    assert entry.before == {"role": "patient", "hospital": None}
    assert entry.after == {"role": "nurse", "hospital": "Seaview Hospital"}


def test_moving_staff_to_another_hospital_logs_only_the_hospital(admin_client, make_user, make_hospital):
    first, second = make_hospital(), make_hospital(name="Seaview Hospital")
    nurse = make_user(Role.NURSE, hospital=first)
    assert assign(admin_client, nurse.pk, Role.NURSE, second.pk).status_code == 200
    entry = AuditLog.objects.get(action="user.role_changed")
    assert (entry.before, entry.after) == ({"hospital": first.name}, {"hospital": "Seaview Hospital"})


def test_an_admin_needs_no_hospital_and_leaving_it_out_keeps_it(admin_client, make_user, make_hospital):
    hospital = make_hospital()
    doctor = make_user(Role.DOCTOR, hospital=hospital)
    assert assign(admin_client, doctor.pk, Role.ADMIN, None).status_code == 200
    doctor.refresh_from_db()
    assert (doctor.role, doctor.hospital) == (Role.ADMIN, None)
    nurse = make_user(Role.NURSE, email="n2@example.com", hospital=hospital)
    assert change(admin_client, nurse.pk, Role.PHARMACIST).status_code == 200
    nurse.refresh_from_db()
    assert nurse.hospital == hospital


def test_an_unknown_or_inactive_hospital_is_refused(admin_client, make_user, make_hospital):
    closed = make_hospital(name="Closed Hospital", is_active=False)
    patient = make_user(Role.PATIENT, email="new@example.com")
    assert assign(admin_client, patient.pk, Role.NURSE, 999_999).status_code == 400
    response = assign(admin_client, patient.pk, Role.NURSE, closed.pk)
    assert response.status_code == 400 and "hospitalId" in response.json()


def test_staff_without_a_hospital_no_longer_see_every_hospitals_rows(make_user, make_hospital):
    """F11: own_hospital() gave the whole network to anyone without a hospital, not only to admins."""
    from apps.accounts.permissions import own_hospital

    first, second = make_hospital(), make_hospital(name="Seaview Hospital")
    make_user(Role.NURSE, email="a@example.com", hospital=first)
    make_user(Role.NURSE, email="b@example.com", hospital=second)
    unplaced = make_user(Role.NURSE, email="unplaced@example.com")
    network_admin = make_user(Role.ADMIN, email="boss@example.com")
    everyone = User.objects.all()
    assert set(own_hospital(everyone, unplaced)) == set(User.objects.filter(hospital=None))
    assert own_hospital(everyone, network_admin).count() == everyone.count()
    placed = make_user(Role.DOCTOR, hospital=first)
    assert set(own_hospital(everyone, placed)) == set(User.objects.filter(hospital=first))
