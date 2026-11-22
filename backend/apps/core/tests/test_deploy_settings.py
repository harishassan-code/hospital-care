"""B13 deploy hardening. With DEBUG off the app refuses to start without a key, sends HSTS, redirects to HTTPS
(except Render's health check), and passes `check --deploy`. Those settings are read at import time, so each
case runs in a child process (see django_subprocess.py)."""

import json

from apps.core.tests.django_subprocess import manage, python

DEPLOY_SETTINGS = """
import json
from django.conf import settings
print(json.dumps({
    "hsts": settings.SECURE_HSTS_SECONDS,
    "subdomains": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "preload": settings.SECURE_HSTS_PRELOAD,
    "redirect": settings.SECURE_SSL_REDIRECT,
    "exempt": settings.SECURE_REDIRECT_EXEMPT,
}))
"""

REDIRECTS = """
import json
import django
django.setup()
from django.test import Client
client = Client()
health = client.get("/api/health/", HTTP_HOST="localhost")
other = client.get("/api/auth/me/", HTTP_HOST="localhost")
print(json.dumps({
    "health": health.status_code,
    "other": other.status_code,
    "location": other.get("Location", ""),
}))
"""


def test_deploy_check_is_clean_with_debug_off_and_a_long_key():
    result = manage("check", "--deploy", "--fail-level", "WARNING")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no issues" in result.stdout


def test_the_app_refuses_to_start_without_a_secret_key():
    for value in (None, ""):  # unset, or set to nothing
        result = manage("check", env={"DJANGO_SECRET_KEY": value})
        assert result.returncode != 0
        assert "DJANGO_SECRET_KEY must be set" in result.stderr


def test_https_and_hsts_are_on_with_debug_off():
    result = python(DEPLOY_SETTINGS)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "hsts": 3600,
        "subdomains": True,
        "preload": False,
        "redirect": True,
        "exempt": [r"^api/health/$"],
    }


def test_hsts_length_comes_from_the_environment():
    result = python(DEPLOY_SETTINGS, env={"DJANGO_HSTS_SECONDS": "31536000"})
    assert json.loads(result.stdout)["hsts"] == 31536000


def test_a_bad_hsts_length_stops_the_server_and_names_the_variable():
    result = python(DEPLOY_SETTINGS, env={"DJANGO_HSTS_SECONDS": "a week"})
    assert result.returncode != 0
    assert "DJANGO_HSTS_SECONDS must be a whole number" in result.stderr


def test_health_check_is_not_redirected_but_the_rest_of_the_api_is():
    result = python(REDIRECTS)
    assert result.returncode == 0, result.stderr
    seen = json.loads(result.stdout)
    assert seen["health"] == 200
    assert seen["other"] == 301
    assert seen["location"] == "https://localhost/api/auth/me/"


def test_hsts_and_the_https_redirect_are_off_under_the_test_suite(settings):
    """Local development and the tests run with DEBUG on, so they see no change."""
    assert settings.SECURE_HSTS_SECONDS == 0
    assert settings.SECURE_SSL_REDIRECT is False
