import pytest
from django.urls import reverse

from apps.accounts.models import Role, User
from conftest import PASSWORD

pytestmark = pytest.mark.django_db

SIGNUP = {
    "full_name": "Sara Ali Khan",
    "email": "Sara@Example.com",
    "phone": "+92 300 1234567",
    "password": "Clinic-visit-9",
}


def test_signup_creates_patient_with_lowercased_email(api):
    res = api.post(reverse("auth-signup"), SIGNUP, format="json")
    assert res.status_code == 201
    user = User.objects.get(email="sara@example.com")
    assert user.role == Role.PATIENT
    assert (user.first_name, user.last_name) == ("Sara", "Ali Khan")
    assert res.json()["role"] == "patient"


def test_signup_cannot_choose_a_staff_role(api):
    api.post(reverse("auth-signup"), {**SIGNUP, "role": "admin"}, format="json")
    assert User.objects.get(email="sara@example.com").role == Role.PATIENT


def test_signup_with_taken_email_any_case_is_rejected_on_email(api, make_user):
    make_user(email="sara@example.com")
    res = api.post(reverse("auth-signup"), SIGNUP, format="json")
    assert res.status_code == 400
    assert "email" in res.json()


@pytest.mark.parametrize("password", ["short1", "12345678901", "password"])
def test_signup_rejects_weak_passwords(api, password):
    res = api.post(reverse("auth-signup"), {**SIGNUP, "password": password}, format="json")
    assert res.status_code == 400
    assert "password" in res.json()


def test_signup_rejects_bad_phone(api):
    res = api.post(reverse("auth-signup"), {**SIGNUP, "phone": "call me"}, format="json")
    assert res.status_code == 400


def test_login_me_logout_round_trip(api, make_user):
    make_user(Role.NURSE, email="nurse@example.com")
    res = api.post(reverse("auth-login"), {"email": "NURSE@example.com", "password": PASSWORD}, format="json")
    assert res.status_code == 200
    assert res.json()["role"] == "nurse"
    assert "csrftoken" in res.cookies

    me = api.get(reverse("auth-me"))
    assert me.status_code == 200 and me.json()["email"] == "nurse@example.com"

    # Signed-in POSTs need the CSRF token, exactly as the frontend sends it.
    token = api.cookies["csrftoken"].value
    assert api.post(reverse("auth-logout")).status_code == 403
    assert api.post(reverse("auth-logout"), HTTP_X_CSRFTOKEN=token).status_code == 204
    assert api.get(reverse("auth-me")).status_code == 403


def test_wrong_password_and_unknown_email_look_the_same(api, make_user):
    make_user(email="real@example.com")
    wrong = api.post(reverse("auth-login"), {"email": "real@example.com", "password": "nope"}, format="json")
    unknown = api.post(
        reverse("auth-login"), {"email": "ghost@example.com", "password": "nope"}, format="json"
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_inactive_user_cannot_log_in(api, make_user):
    make_user(email="gone@example.com", is_active=False)
    res = api.post(reverse("auth-login"), {"email": "gone@example.com", "password": PASSWORD}, format="json")
    assert res.status_code == 401


def test_csrf_endpoint_sets_cookie(api):
    res = api.get(reverse("auth-csrf"))
    assert res.status_code == 200 and "csrftoken" in res.cookies


def test_superuser_acts_as_admin(make_user):
    assert make_user(Role.PATIENT, email="root@example.com", is_superuser=True).effective_role == Role.ADMIN
