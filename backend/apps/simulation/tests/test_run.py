"""The simulation on the demo network (B21): three city hours, the first hour by hour (a fast-forward) and the
last two step by step, through the same path a tick takes on staging."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command

from apps.audit.models import AuditLog
from apps.blood.models import BloodUnit
from apps.emergencies.models import ErVisit
from apps.emergencies.services import create_case
from apps.hospitals.models import Bed, BedStatus
from apps.matching.models import Reservation
from apps.metrics.models import MetricSnapshot
from apps.simulation import engine
from apps.simulation.actor import SYSTEM_EMAIL
from apps.simulation.models import SimulationState

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo(settings):
    call_command("seed_demo", verbosity=0)
    settings.SIMULATION_ENABLED = True
    return engine.state()


def run_for(hours: float):
    state = engine.state()
    SimulationState.objects.filter(pk=1).update(
        fast_forward_from=state.progress, fast_forward_to=state.progress + timedelta(hours=hours)
    )
    while engine.run(force=True, budget=120).get("behind"):
        pass


def test_three_hours_of_the_city(demo):
    from apps.accounts.models import User

    nurse = User.objects.get(username="nurse@demo.citycare.pk")
    case = create_case(
        severity="high",
        patient_ref="P-1",
        items=[{"type": "bed", "bedType": "general", "quantity": 1}],
        actor=nurse,
    )
    held_bed = Bed.objects.filter(hospital=nurse.hospital, status=BedStatus.FREE, bed_type="general").first()
    Reservation.objects.create(
        request_item=case.items.first(),
        content_type=ContentType.objects.get_for_model(Bed),
        object_id=held_bed.pk,
        hospital=nurse.hospital,
        reserved_by=nurse,
        expires_at=demo.progress + timedelta(days=1),
    )
    demo_units = dict(BloodUnit.objects.filter(demo_stock=True).values_list("pk", "status"))
    assert demo_units  # the scenario's O- red cells are flagged
    snapshots = MetricSnapshot.objects.count()

    run_for(3)

    state = engine.state()
    assert state.fast_forward_to is None and state.progress == state.anchor_city
    assert ErVisit.objects.exists()
    assert MetricSnapshot.objects.count() > snapshots  # the charts carry on
    assert dict(BloodUnit.objects.filter(demo_stock=True).values_list("pk", "status")) == demo_units
    held_bed.refresh_from_db()
    assert held_bed.status == BedStatus.FREE
    case.refresh_from_db()
    assert case.status == "open"  # a person's case: the simulation never moves it
    simulated = AuditLog.objects.filter(actor_email=SYSTEM_EMAIL)
    assert simulated.filter(action="simulation.fast_forwarded").count() == 1
    assert simulated.filter(action="ervisit.arrived").exists()


def test_one_tick_at_a_time(demo):
    from django.utils import timezone

    SimulationState.objects.filter(pk=1).update(lease_until=timezone.now() + timedelta(seconds=30))
    assert engine.run(force=True) == {"ran": False, "reason": "busy"}


def test_a_paused_city_does_not_move(demo):
    SimulationState.objects.filter(pk=1).update(paused=True)
    assert engine.run(force=True)["reason"] == "paused"


def test_a_reset_returns_to_the_real_clock(demo):
    run_for(1)
    call_command("seed_demo", reset=True, verbosity=0)
    assert not SimulationState.objects.exists()
    assert not ErVisit.objects.exists()
