"""B13 deploy hardening. With DEBUG off the app refuses to start without a key, sends HSTS, redirects to HTTPS
(except the health check), and passes `check --deploy`. Those settings are read at import time, so each
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


# Staging on Vercel (B14). Vercel sets VERCEL=1 while it builds and runs the app; the project sets only the
# key and the database, so the defaults below have to be right on their own.
VERCEL_SETTINGS = """
import json
from django.conf import settings
print(json.dumps({
    "debug": settings.DEBUG,
    "hosts": settings.ALLOWED_HOSTS,
    "cache": settings.CACHES["default"]["BACKEND"],
    "proxies": settings.TRUSTED_PROXY_COUNT,
    "server_side_cursors_off": settings.DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"],
}))
"""

ON_VERCEL = {"VERCEL": "1", "DJANGO_DEBUG": None}


def test_on_vercel_debug_is_off_and_the_rest_defaults_to_vercel():
    result = python(VERCEL_SETTINGS, env=ON_VERCEL)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "debug": False,
        "hosts": [".vercel.app"],
        # Several copies of the app run at once, so sign-in limits and lockouts are counted in the database.
        "cache": "django.core.cache.backends.db.DatabaseCache",
        "proxies": 1,
        "server_side_cursors_off": True,
    }


def test_on_vercel_the_deploy_check_passes_with_only_a_key_set():
    result = manage("check", "--deploy", "--fail-level", "WARNING", env=ON_VERCEL)
    assert result.returncode == 0, result.stdout + result.stderr


def test_on_vercel_a_missing_key_still_stops_the_app():
    result = manage("check", env={**ON_VERCEL, "DJANGO_SECRET_KEY": None})
    assert result.returncode != 0
    assert "DJANGO_SECRET_KEY must be set" in result.stderr


def test_on_vercel_each_default_can_be_overridden():
    overrides = {
        **ON_VERCEL,
        "DJANGO_ALLOWED_HOSTS": "citycare.example.org",
        "DJANGO_CACHE": "memory",
        "DJANGO_TRUSTED_PROXY_COUNT": "2",
    }
    result = python(VERCEL_SETTINGS, env=overrides)
    assert result.returncode == 0, result.stderr
    seen = json.loads(result.stdout)
    assert seen["hosts"] == ["citycare.example.org"]
    assert seen["cache"] == "django.core.cache.backends.locmem.LocMemCache"
    assert seen["proxies"] == 2


def test_off_vercel_nothing_changes():
    result = python(VERCEL_SETTINGS, env={"DJANGO_ALLOWED_HOSTS": None})
    assert result.returncode == 0, result.stderr
    seen = json.loads(result.stdout)
    assert seen["hosts"] == ["localhost", "127.0.0.1"]
    assert seen["cache"] == "django.core.cache.backends.locmem.LocMemCache"
    assert seen["proxies"] == 0
    assert seen["server_side_cursors_off"] is False
