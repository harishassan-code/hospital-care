"""Story #58: every API view names a role-based permission, so a new endpoint can't ship open by accident."""

from django.urls import URLPattern, URLResolver, get_resolver
from rest_framework.permissions import AllowAny, IsAuthenticated

# Views anyone may call: health, sign-in and sign-up, and the public landing data. Anything else must name a
# permission class narrower than "signed in".
PUBLIC = {
    "health",
    "LoginView",
    "LogoutView",
    "SignupView",
    "CsrfView",
    "PublicStatusView",
}
# Views that only need a signed-in user, by design (the user's own account and settings).
SIGNED_IN_ONLY = {"MeView", "ChangePasswordView", "PasswordView", "ProfileView"}
# Views whose rule depends on the resource type in the request, so they check it in the view or service
# (can_see / can_edit on the type's module, plus own_hospital); see apps/matching/views.py.
CHECKED_PER_TYPE = {"HeldReservationListView", "ReservationAllocateView", "ReservationAllocateManyView"}


def _views(resolver=None, prefix=""):
    for pattern in (resolver or get_resolver()).url_patterns:
        if isinstance(pattern, URLResolver):
            yield from _views(pattern, prefix + str(pattern.pattern))
        elif isinstance(pattern, URLPattern):
            view = getattr(pattern.callback, "cls", None)
            if view is not None:
                yield prefix + str(pattern.pattern), view


def test_every_api_view_names_a_role_based_permission():
    loose = []
    for route, view in _views():
        if not route.startswith("api/"):
            continue
        name = getattr(view, "__name__", "")
        classes = list(getattr(view, "permission_classes", []))
        if name in PUBLIC:
            continue
        if not classes or classes == [AllowAny]:
            loose.append(f"{route} ({name}) is open to anyone")
        elif classes == [IsAuthenticated] and name not in SIGNED_IN_ONLY | CHECKED_PER_TYPE:
            loose.append(f"{route} ({name}) only checks sign-in")
    assert not loose, "\n".join(loose)
