import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User

PASSWORD = "Strong-pass-123"


@pytest.fixture
def api():
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def make_user(db):
    def make(role=Role.PATIENT, email=None, **extra):
        email = email or f"{role.lower()}@example.com"
        return User.objects.create_user(username=email, email=email, password=PASSWORD, role=role, **extra)

    return make


@pytest.fixture
def client_as(make_user):
    """An API client already signed in with the given role."""

    def signed_in(role):
        client = APIClient()
        client.force_authenticate(make_user(role))
        return client

    return signed_in
