"""Story #55: GET /api/command-centre/ is for admins only, is read-only, and runs the sweeps first."""

from datetime import timedelta

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.blood.models import UnitStatus
from apps.emergencies.models import EmergencyRequest, RequestStatusChange
from apps.matching.models import ReservationStatus
from apps.matching.tests.reservation_support import bed_need, blood_need, case, hold, staff, unit

from .support import stocked_hospital

pytestmark = pytest.mark.django_db

URL = reverse("command-centre")


def row(body, name):
    return next(h for h in body["hospitals"] if h["name"] == name)


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_only_admins_get_the_figures(client_as, role):
    assert client_as(role).get(URL).status_code == 403


def test_signed_out_callers_are_refused(api):
    assert api.get(URL).status_code == 403


def test_admin_gets_the_network_without_a_hospital_of_their_own(client_as, make_hospital, make_user):
    stocked_hospital(make_hospital("Civic General"), make_user)
    response = client_as(Role.ADMIN).get(URL)
    assert response.status_code == 200
    assert [h["name"] for h in response.json()["hospitals"]] == ["Civic General"]


def test_the_endpoint_is_read_only_even_for_admins(client_as):
    """The module is view-only, so a write is refused (403) whoever sends it."""
    assert client_as(Role.ADMIN).post(URL, {}, format="json").status_code == 403


def test_an_overdue_critical_case_is_escalated_before_the_figures_are_worked_out(client_as, make_hospital):
    hospital = make_hospital("Civic General")
    overdue = case(hospital, bed_need("icu"), status="open", severity="critical")
    RequestStatusChange.objects.create(
        request=overdue,
        from_status="",
        to_status="open",
        action="create",
        at=timezone.now() - timedelta(minutes=settings.EMERGENCY_ESCALATION_MINUTES + 15),
    )
    body = client_as(Role.ADMIN).get(URL).json()
    assert row(body, "Civic General")["cases"] == {"active": 1, "escalated": 1}
    assert EmergencyRequest.objects.get(pk=overdue.pk).status == "escalated"


def test_an_expired_hold_goes_back_to_stock_before_the_figures_are_worked_out(
    client_as, make_hospital, make_user
):
    hospital = make_hospital("Civic General")
    nurse = staff(make_user, hospital)
    needed = case(hospital, blood_need("A+", quantity=1))
    freed = unit(hospital, group="A+", status=UnitStatus.RESERVED)
    expired = hold(needed.items.get(), freed, hospital=hospital, actor=nurse, expires_in_minutes=-5)

    body = client_as(Role.ADMIN).get(URL).json()

    a_plus = next(r for r in row(body, "Civic General")["redCells"] if r["group"] == "A+")
    assert a_plus["available"] == 1
    expired.refresh_from_db()
    assert expired.status == ReservationStatus.EXPIRED
    freed.refresh_from_db()
    assert freed.status == UnitStatus.AVAILABLE
