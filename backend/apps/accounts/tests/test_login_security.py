"""Login security cases from the QA sheet (LOGIN-N03, N04, N07, N14), against the real API."""

import pytest
from django.urls import reverse

from apps.accounts.models import Role, User
from conftest import PASSWORD

LOGIN = reverse("auth-login")


def attempt(api, email, password):
    return api.post(LOGIN, {"email": email, "password": password}, format="json")


@pytest.mark.django_db
class TestLockout:
    """LOGIN-N03: repeated failed logins on one account are stopped for a while."""

    def test_locks_the_account_after_five_failed_attempts(self, api, make_user):
        user = make_user(Role.NURSE)
        for _ in range(5):
            assert attempt(api, user.email, "wrong-password").status_code == 401
        locked = attempt(api, user.email, PASSWORD)
        assert locked.status_code == 429
        assert "Too many failed sign-in attempts" in locked.json()["detail"]

    def test_counts_the_account_whatever_the_email_case(self, api, make_user):
        user = make_user(Role.NURSE)
        for _ in range(5):
            attempt(api, user.email.upper(), "wrong-password")
        assert attempt(api, user.email, PASSWORD).status_code == 429

    def test_a_successful_login_resets_the_count(self, api, make_user):
        user = make_user(Role.NURSE)
        for _ in range(4):
            attempt(api, user.email, "wrong-password")
        assert attempt(api, user.email, PASSWORD).status_code == 200
        api.post(reverse("auth-logout"), HTTP_X_CSRFTOKEN=api.cookies["csrftoken"].value)
        assert attempt(api, user.email, "wrong-password").status_code == 401
        assert attempt(api, user.email, PASSWORD).status_code == 200

    def test_other_accounts_are_not_affected(self, api, make_user):
        locked, other = make_user(Role.NURSE), make_user(Role.DOCTOR)
        for _ in range(5):
            attempt(api, locked.email, "wrong-password")
        assert attempt(api, other.email, PASSWORD).status_code == 200


@pytest.mark.django_db
def test_sql_injection_payloads_are_refused_without_side_effects(api, make_user):
    """LOGIN-N04: injection strings are just wrong credentials; nothing is changed or exposed."""
    make_user(Role.ADMIN)
    before = User.objects.count()
    payloads = [
        ("' OR '1'='1", "admin'--"),
        ("admin@example.com' --", "x"),
        ("a@b.co", "' OR 1=1; DROP TABLE accounts_user; --"),
    ]
    for email, password in payloads:
        response = attempt(api, email, password)
        assert response.status_code in (400, 401)
        assert response.json() == {"detail": "That email and password don't match an account."}
    assert User.objects.count() == before
    assert api.get(reverse("auth-me")).status_code == 403


@pytest.mark.django_db
def test_deactivated_accounts_cannot_sign_in(api, make_user):
    """LOGIN-N07: a deactivated account is refused with the same generic message (no account discovery)."""
    user = make_user(Role.NURSE, is_active=False)
    response = attempt(api, user.email, PASSWORD)
    assert response.status_code == 401
    assert response.json() == {"detail": "That email and password don't match an account."}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("email", "password"),
    [("a" * 250 + "@x.co", PASSWORD), ("nurse@example.com", "x" * 513)],
    ids=["email over 254 characters", "password over 512 characters"],
)
def test_oversized_credentials_are_rejected_before_checking(api, make_user, email, password):
    """LOGIN-N14: oversized input is refused as bad input, without running the password hasher on it."""
    make_user(Role.NURSE)
    response = attempt(api, email, password)
    assert response.status_code == 400
