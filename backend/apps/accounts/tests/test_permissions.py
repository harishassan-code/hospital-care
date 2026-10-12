"""Story 1.2 Access control: every endpoint declares its permissions; each role gets exactly its access."""

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.accounts.models import Role
from apps.accounts.permissions import ACCESS, EDIT
from apps.hospitals.models import Bed, BedStatus, Ward

pytestmark = pytest.mark.django_db


def api_views(patterns=None, prefix=""):
    for p in patterns if patterns is not None else get_resolver().url_patterns:
        route = prefix + str(p.pattern)
        if isinstance(p, URLResolver):
            yield from api_views(p.url_patterns, route)
        elif isinstance(p, URLPattern) and route.startswith("api/"):
            yield route, p.callback


def test_every_api_endpoint_declares_its_permission_classes():
    views = list(api_views())
    assert len(views) >= 18
    for route, callback in views:
        view_class = callback.cls
        assert "permission_classes" in vars(view_class), f"{route} relies on the default permission"


# (module, method, url name, url args, body) for one read and one write per module.
ENDPOINTS = [
    ("beds", "get", "bed-board", [], None),
    ("blood", "get", "blood-units", [], None),
    ("pharmacy", "get", "pharmacy-stock", [], None),
    ("hospitals", "get", "hospital-list", [], None),
    ("hospitals", "get", "capability-list", [], None),
    ("hospitals", "post", "hospital-list", [], {}),
    ("users", "get", "user-list", [], None),
    ("users", "patch", "user-role", [999], {"role": "doctor"}),
]


@pytest.mark.parametrize("role", list(Role))
@pytest.mark.parametrize(("module", "method", "name", "args", "body"), ENDPOINTS)
def test_each_role_gets_exactly_its_access(client_as, role, module, method, name, args, body):
    client = client_as(role)
    url = reverse(name, args=args)
    response = getattr(client, method)(url, body, format="json") if body is not None else client.get(url)
    needed = EDIT if method != "get" else None
    allowed = module in ACCESS[role] and (needed is None or ACCESS[role][module] == EDIT)
    # Allowed calls may still fail validation (400) or find nothing (404), but never 403.
    assert (response.status_code == 403) is not allowed, (role, method, name, response.status_code)


@pytest.mark.parametrize(("module", "method", "name", "args", "body"), ENDPOINTS)
def test_signed_out_callers_are_refused(api, module, method, name, args, body):
    url = reverse(name, args=args)
    response = getattr(api, method)(url, body or {}, format="json") if method != "get" else api.get(url)
    assert response.status_code == 403


class TestOwnHospitalOnly:
    """Staff can only modify resources belonging to their own hospital; admins manage the network."""

    @pytest.fixture
    def beds(self, make_hospital):
        here, there = make_hospital("Here"), make_hospital("There")
        for hospital, label in ((here, "H-01"), (there, "T-01")):
            ward = Ward.objects.create(code=f"w{hospital.pk}", name="Ward", kind="General", hospital=hospital)
            Bed.objects.create(ward=ward, label=label, status=BedStatus.FREE)
        return here, there

    def act(self, client, label):
        return client.post(reverse("bed-action", args=[label]), {"action": "reserve"}, format="json")

    def test_nurse_changes_beds_in_her_hospital_only(self, client_as, beds):
        here, _ = beds
        nurse = client_as(Role.NURSE, hospital=here)
        assert self.act(nurse, "H-01").status_code == 200
        response = self.act(nurse, "T-01")
        assert response.status_code == 403
        assert Bed.objects.get(label="T-01").status == BedStatus.FREE

    def test_admin_changes_beds_anywhere(self, client_as, beds):
        here, _ = beds
        admin = client_as(Role.ADMIN, hospital=here)
        assert self.act(admin, "T-01").status_code == 200

    def test_bed_board_shows_only_the_users_hospital(self, client_as, beds):
        here, _ = beds
        data = client_as(Role.DOCTOR, hospital=here).get(reverse("bed-board")).json()
        assert [b["id"] for b in data["beds"]] == ["H-01"]
        assert [w["id"] for w in data["wards"]] == [f"w{here.pk}"]
