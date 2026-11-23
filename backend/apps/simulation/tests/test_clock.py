"""The city clock (B21): real time with the simulation off; speed, pause and fast-forward with it on."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.core import clock
from apps.simulation.models import SimulationState

pytestmark = pytest.mark.django_db

REAL = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)


def at_real(moment):
    return patch("django.utils.timezone.now", return_value=moment)


def test_with_the_simulation_off_the_clock_is_the_real_one(settings):
    settings.SIMULATION_ENABLED = False
    SimulationState.objects.create(pk=1, anchor_real=REAL, anchor_city=REAL + timedelta(days=3))
    with at_real(REAL):
        assert clock.now() == REAL


def test_the_clock_runs_at_its_speed_from_its_anchor(settings):
    settings.SIMULATION_ENABLED = True
    SimulationState.objects.create(pk=1, anchor_real=REAL, anchor_city=REAL + timedelta(hours=1), speed=10)
    with at_real(REAL + timedelta(minutes=6)):
        assert clock.now() == REAL + timedelta(hours=2)  # an hour ahead, plus 6 real minutes × 10
        assert clock.reading().mode == "live"


def test_a_paused_clock_stands_still(settings):
    settings.SIMULATION_ENABLED = True
    SimulationState.objects.create(pk=1, anchor_real=REAL, anchor_city=REAL, paused=True)
    with at_real(REAL + timedelta(hours=5)):
        assert clock.now() == REAL
        assert clock.reading().mode == "paused"


def test_during_a_fast_forward_the_clock_follows_the_engine(settings):
    settings.SIMULATION_ENABLED = True
    SimulationState.objects.create(
        pk=1,
        anchor_real=REAL,
        anchor_city=REAL,
        progress=REAL + timedelta(days=2),
        fast_forward_from=REAL,
        fast_forward_to=REAL + timedelta(days=7),
    )
    with at_real(REAL + timedelta(seconds=30)):
        assert clock.now() == REAL + timedelta(days=2)
        assert clock.reading().mode == "fastForward"


def test_a_step_stamps_its_own_time_and_sign_in_keeps_the_real_clock(settings):
    settings.SIMULATION_ENABLED = True
    SimulationState.objects.create(pk=1, anchor_real=REAL, anchor_city=REAL + timedelta(days=1))
    with at_real(REAL), clock.at(REAL + timedelta(days=5)):
        assert clock.now() == REAL + timedelta(days=5)
        from django.utils import timezone

        assert timezone.now() == REAL  # sessions, sign-in limits and the cache use this one
    with at_real(REAL):
        assert clock.now() == REAL + timedelta(days=1)


def test_api_responses_carry_the_city_clock_only_while_it_runs(settings, client):
    settings.SIMULATION_ENABLED = False
    response = client.get(reverse("health"))
    assert "X-City-Time" not in response.headers
    settings.SIMULATION_ENABLED = True
    SimulationState.objects.create(pk=1, anchor_real=REAL, anchor_city=REAL + timedelta(days=1), speed=5)
    clock.forget()
    with at_real(REAL):
        response = client.get(reverse("health"))
    assert response.headers["X-City-Time"].startswith("2026-11-24T09:00")
    assert response.headers["X-City-Mode"] == "live"
    assert response.headers["X-City-Speed"] == "5"


def test_audit_entries_keep_the_real_time_beside_the_city_time(settings, make_user):
    from apps.audit.services import record

    settings.SIMULATION_ENABLED = True
    SimulationState.objects.create(pk=1, anchor_real=REAL, anchor_city=REAL + timedelta(days=4))
    user = make_user("admin")
    with at_real(REAL):
        entry = record(user, "user.updated", user)
    assert entry.at == REAL + timedelta(days=4)
    assert entry.recorded_at == REAL
