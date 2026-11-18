"""B13 F4 (spec Q10): sign-in and sign-up are limited per client address, so one machine can't try
thousands of passwords or create thousands of accounts. The address comes from X-Forwarded-For only behind
the proxies the deployment runs (DJANGO_TRUSTED_PROXY_COUNT), never from a header the client alone sets."""

import pytest
from django.urls import reverse

from apps.accounts.throttles import client_address
from apps.core.tests.django_subprocess import manage
from conftest import PASSWORD

pytestmark = pytest.mark.django_db

LOGIN = reverse("auth-login")
SIGNUP = reverse("auth-signup")
ADDRESS = "203.0.113.5"


@pytest.fixture
def limits(settings):
    settings.AUTH_THROTTLE_RATES = {"auth_login": "3/min", "auth_signup": "2/hour"}
    settings.TRUSTED_PROXY_COUNT = 0


def sign_in(api, email, address=ADDRESS, **headers):
    body = {"email": email, "password": "wrong-password"}
    return api.post(LOGIN, body, format="json", REMOTE_ADDR=address, **headers)


def sign_up(api, number, address=ADDRESS, **headers):
    body = {"full_name": "Test Person", "email": f"new{number}@example.com", "password": PASSWORD}
    return api.post(SIGNUP, body, format="json", REMOTE_ADDR=address, **headers)


def throttled(response):
    return response.status_code == 429 and "throttled" in response.json()["detail"]


def test_sign_in_is_limited_per_client_address(api, limits):
    for number in range(3):
        assert sign_in(api, f"a{number}@example.com").status_code == 401
    assert throttled(sign_in(api, "a9@example.com"))
    assert sign_in(api, "b@example.com", address="203.0.113.6").status_code == 401  # another address


def test_sign_up_is_limited_per_client_address(api, limits):
    assert sign_up(api, 1).status_code == 201
    assert sign_up(api, 2).status_code == 201
    assert throttled(sign_up(api, 3))
    assert sign_up(api, 4, address="203.0.113.6").status_code == 201  # another address


def test_with_a_trusted_proxy_the_client_is_the_address_the_proxy_recorded(api, limits, settings):
    """Behind one proxy the last X-Forwarded-For entry is the client. A client that sends its own first entry
    gets no new bucket: the proxy appended the real address after whatever the client sent."""
    settings.TRUSTED_PROXY_COUNT = 1
    proxy = "10.0.0.9"
    for number, spoofed in enumerate(["198.51.100.1", "198.51.100.2", "198.51.100.3"]):
        sign_in(api, f"c{number}@example.com", address=proxy, HTTP_X_FORWARDED_FOR=f"{spoofed}, 203.0.113.7")
    assert throttled(
        sign_in(api, "d@example.com", address=proxy, HTTP_X_FORWARDED_FOR="198.51.100.4, 203.0.113.7")
    )
    other_client = sign_in(api, "e@example.com", address=proxy, HTTP_X_FORWARDED_FOR="203.0.113.8")
    assert other_client.status_code == 401  # a different client behind the same proxy is not affected


def test_without_a_trusted_proxy_the_forwarded_header_is_ignored(api, limits):
    """Without a proxy the header is client-controlled, so every request counts against REMOTE_ADDR."""
    for number, spoofed in enumerate(["198.51.100.1", "198.51.100.2", "198.51.100.3"]):
        sign_in(api, f"f{number}@example.com", HTTP_X_FORWARDED_FOR=spoofed)
    assert throttled(sign_in(api, "g@example.com", HTTP_X_FORWARDED_FOR="198.51.100.9"))


def test_an_empty_rate_turns_the_limit_off(api, settings):
    settings.AUTH_THROTTLE_RATES = {"auth_login": "", "auth_signup": ""}
    for number in range(6):
        assert sign_in(api, f"h{number}@example.com").status_code == 401


def test_the_client_address_is_the_nearest_trusted_entry(rf, settings):
    settings.TRUSTED_PROXY_COUNT = 2
    request = rf.post("/", HTTP_X_FORWARDED_FOR="198.51.100.1, 203.0.113.7, 10.1.1.1", REMOTE_ADDR="10.0.0.9")
    assert client_address(request) == "203.0.113.7"


def test_the_client_address_falls_back_to_remote_addr_when_the_header_is_short(rf, settings):
    settings.TRUSTED_PROXY_COUNT = 2
    request = rf.post("/", HTTP_X_FORWARDED_FOR="203.0.113.7", REMOTE_ADDR="10.0.0.9")
    assert client_address(request) == "10.0.0.9"


def test_the_client_address_ignores_the_header_without_proxies(rf, settings):
    settings.TRUSTED_PROXY_COUNT = 0
    request = rf.post("/", HTTP_X_FORWARDED_FOR="198.51.100.1", REMOTE_ADDR="10.0.0.9")
    assert client_address(request) == "10.0.0.9"


BAD_SETTINGS = [
    ("DJANGO_LOGIN_THROTTLE", "lots"),
    ("DJANGO_SIGNUP_THROTTLE", "30 per minute"),
    ("DJANGO_TRUSTED_PROXY_COUNT", "-1"),
]


@pytest.mark.parametrize(("name", "value"), BAD_SETTINGS)
def test_a_bad_throttle_setting_stops_the_server_and_names_it(name, value):
    result = manage("check", env={name: value})
    assert result.returncode != 0
    assert name in result.stderr
