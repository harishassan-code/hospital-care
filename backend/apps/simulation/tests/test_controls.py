"""The CityCare admin's Simulation panel (B21): who may use it, and what each control does."""

from datetime import timedelta

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.simulation.models import SimEvent, SimulationState

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def on(settings):
    settings.SIMULATION_ENABLED = True


@pytest.fixture
def network_admin(client_as):
    return client_as(Role.ADMIN, email="network@example.com")


def control(client, action, value=""):
    return client.post(reverse("simulation-control"), {"action": action, "value": value}, format="json")


def test_only_the_network_admin_runs_the_clock(client_as, make_hospital, network_admin):
    hospital = make_hospital()
    assert network_admin.get(reverse("simulation")).status_code == 200
    hospital_admin = client_as(Role.ADMIN, email="hadmin@example.com", hospital=hospital)
    assert hospital_admin.get(reverse("simulation")).status_code == 403
    assert control(hospital_admin, "pause").status_code == 403
    assert client_as(Role.NURSE, hospital=hospital).get(reverse("simulation")).status_code == 403
    assert APIClient().get(reverse("simulation")).status_code == 403
    assert control(APIClient(), "pause").status_code == 403


def test_pause_resume_and_speed_are_audited_and_listed(network_admin):
    assert control(network_admin, "pause").json()["mode"] == "paused"
    body = control(network_admin, "resume").json()
    assert body["mode"] == "live" and body["paused"] is False
    body = control(network_admin, "speed", "10").json()
    assert body["speed"] == 10
    actions = list(AuditLog.objects.filter(action__startswith="simulation.").values_list("action", flat=True))
    assert sorted(actions) == ["simulation.pause", "simulation.resume", "simulation.speed"]
    assert body["events"][0]["message"] == "City clock at 10× real time."


@pytest.mark.parametrize(
    ("action", "value"), [("speed", "3"), ("speed", "fast"), ("fastForward", "3d"), ("scenario", "winter")]
)
def test_values_outside_the_choices_are_refused(network_admin, action, value):
    assert control(network_admin, action, value).status_code == 400
    assert not AuditLog.objects.filter(action__startswith="simulation.").exists()


def test_a_fast_forward_moves_the_clock_only_as_far_as_the_city_has_run(network_admin):
    body = control(network_admin, "fastForward", "1d").json()
    assert body["mode"] == "fastForward"
    span = body["fastForward"]
    assert span["percent"] == 0
    state = SimulationState.objects.get(pk=1)
    assert state.fast_forward_to - state.fast_forward_from == timedelta(days=1)
    assert control(network_admin, "speed", "2").status_code == 400  # wait for it to finish


def test_catching_up_needs_a_clock_behind_the_real_one(network_admin):
    assert control(network_admin, "catchUp").status_code == 400


def test_scenarios_and_a_mass_casualty_event(network_admin, make_hospital):
    from apps.hospitals.models import Bed, BedType, Department, Ward

    hospital = make_hospital()
    ward = Ward.objects.create(
        code="ed",
        hospital=hospital,
        name="Emergency",
        kind="Emergency department",
        department=Department.objects.create(hospital=hospital, name="Emergency medicine"),
    )
    Bed.objects.create(label="ED-01", ward=ward, bed_type=BedType.EMERGENCY)
    Ward.objects.create(code="medA", hospital=hospital, name="Medical A", kind="General medicine")
    Bed.objects.create(label="MA-01", ward=Ward.objects.get(code="medA"))
    assert control(network_admin, "scenario", "flu").json()["scenario"] == "flu"
    body = control(network_admin, "massCasualty").json()
    assert body["incident"]["hospitals"] == [hospital.name]
    assert control(network_admin, "massCasualty").status_code == 400  # one at a time
    assert control(network_admin, "endIncident").json()["incident"] is None
    assert SimEvent.objects.filter(kind="incident.started").exists()


def test_the_tick_is_open_and_cheap_when_too_soon(settings):
    anyone = APIClient(enforce_csrf_checks=True)
    first = anyone.post(reverse("simulation-tick"))
    assert first.status_code == 200 and first.json()["ran"] is True
    again = anyone.post(reverse("simulation-tick")).json()
    assert again["ran"] is False and again["mode"] == "live"


def test_the_tick_does_nothing_with_the_simulation_off(settings):
    settings.SIMULATION_ENABLED = False
    body = APIClient().post(reverse("simulation-tick")).json()
    assert body["ran"] is False
    assert not SimulationState.objects.exists()
