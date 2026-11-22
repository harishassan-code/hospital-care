"""Sign-in and sign-up limits per client address (B13, F4; spec Q10).

Rates come from settings.AUTH_THROTTLE_RATES, so each can change without a deploy, and an empty rate turns its
limit off. The address comes from X-Forwarded-For only as far as the proxies the deployment runs recorded it
(settings.TRUSTED_PROXY_COUNT), and otherwise from REMOTE_ADDR.
"""

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


def client_address(request) -> str:
    """The address a limit counts against.

    With N proxies in front of the app, each one appends the address it received the request from. The entry
    N places from the right is therefore the client, as the outermost proxy saw it. The N entries from the
    right were all written by proxies we run, whatever the client sent. With no proxy, the header is whatever
    the client wrote, so REMOTE_ADDR is used.
    """
    hops = settings.TRUSTED_PROXY_COUNT
    if hops:
        forwarded = [part.strip() for part in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")]
        forwarded = [part for part in forwarded if part]
        if len(forwarded) >= hops:
            return forwarded[-hops]
    return request.META.get("REMOTE_ADDR", "")


class AuthRateThrottle(SimpleRateThrottle):
    """A limit per client address for one scope. No rate configured means no limit."""

    def get_rate(self):
        return settings.AUTH_THROTTLE_RATES.get(self.scope) or None

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": client_address(request)}


class LoginThrottle(AuthRateThrottle):
    scope = "auth_login"


class SignupThrottle(AuthRateThrottle):
    scope = "auth_signup"
