"""B13 F6 (spec Q7): the Django admin at /admin/ is routed only when DJANGO_ADMIN_ENABLED allows it. On by
default under DEBUG, off otherwise, so the public staging site doesn't offer a superuser login page."""

import json

from django.urls import resolve

from apps.core.tests.django_subprocess import python

ROUTED = """
import json
import django
django.setup()
from django.urls import Resolver404, resolve
try:
    resolve("/admin/login/")
    routed = True
except Resolver404:
    routed = False
print(json.dumps({"routed": routed}))
"""

STATUS = """
import json
import django
django.setup()
from django.test import Client
# Over HTTPS (as Render's proxy presents it), so the SSL redirect doesn't answer first.
response = Client().get("/admin/", HTTP_HOST="localhost", HTTP_X_FORWARDED_PROTO="https")
print(json.dumps({"status": response.status_code, "location": response.get("Location", "")}))
"""


def test_admin_is_not_routed_on_a_debug_off_host_by_default():
    result = python(ROUTED, env={"DJANGO_ADMIN_ENABLED": None})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"routed": False}


def test_admin_is_not_routed_when_switched_off_explicitly():
    result = python(ROUTED, env={"DJANGO_DEBUG": "true", "DJANGO_ADMIN_ENABLED": "false"})
    assert json.loads(result.stdout) == {"routed": False}


def test_admin_answers_404_on_a_debug_off_host_without_the_switch():
    result = python(STATUS, env={"DJANGO_ADMIN_ENABLED": None})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == 404


def test_admin_is_routed_on_a_debug_off_host_when_enabled():
    result = python(STATUS, env={"DJANGO_ADMIN_ENABLED": "true"})
    assert result.returncode == 0, result.stderr
    seen = json.loads(result.stdout)
    assert seen["status"] == 302 and seen["location"].startswith("/admin/login/")


def test_admin_is_routed_under_the_test_suite():
    """Local development and the tests run with DEBUG on, so the admin is there as before."""
    assert resolve("/admin/login/").url_name == "login"
