"""Story 1.1 Login & session security: sessions expire after inactivity."""

import pytest
from django.conf import settings
from django.urls import reverse

from apps.accounts.models import Role
from conftest import PASSWORD

pytestmark = pytest.mark.django_db


def test_sessions_end_after_30_idle_minutes(api, make_user):
    """Story 1.1: sessions expire after inactivity. Each request pushes the expiry back."""
    assert settings.SESSION_COOKIE_AGE == 30 * 60 and settings.SESSION_SAVE_EVERY_REQUEST
    make_user(Role.NURSE, email="hina@example.com")
    api.get(reverse("auth-csrf"))
    api.post(
        reverse("auth-login"),
        {"email": "hina@example.com", "password": PASSWORD},
        format="json",
        HTTP_X_CSRFTOKEN=api.cookies["csrftoken"].value,
    )
    assert api.cookies[settings.SESSION_COOKIE_NAME]["max-age"] == 30 * 60
