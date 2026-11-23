"""The CityCare admin's time controls (B21): pause and resume, speed, fast-forward, the scenario and a
mass-casualty event. Every change is audit-logged and listed in the simulation's events. The clock only ever
moves forward: a fast-forward runs the city through the time it skips, and nothing turns it back (a demo
reset, `seed_demo --reset`, starts again from the real time)."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit.services import record
from apps.core import clock

from . import engine, events
from .models import SimEvent, SimulationState
from .profiles import PROFILES

SPEEDS = [0.5, 1, 2, 5, 10, 60]
FAST_FORWARD_MINUTES = {"30m": 30, "1h": 60, "1d": 24 * 60, "1w": 7 * 24 * 60, "2w": 14 * 24 * 60}
ACTIONS = ["pause", "resume", "speed", "fastForward", "catchUp", "scenario", "massCasualty", "endIncident"]


def _fields(state: SimulationState) -> dict:
    return {
        "paused": state.paused,
        "speed": state.speed,
        "scenario": state.scenario,
        "fastForwardTo": state.fast_forward_to.isoformat() if state.fast_forward_to else None,
        "incidentUntil": state.incident_until.isoformat() if state.incident_until else None,
    }


@transaction.atomic
def apply(action: str, value, *, actor) -> SimulationState:
    if action not in ACTIONS:
        raise ValidationError({"action": [f"Unknown action. Use one of: {', '.join(ACTIONS)}."]})
    engine.state()  # the row exists from here on
    state = SimulationState.objects.select_for_update().get(pk=1)
    before = _fields(state)
    real = timezone.now()
    city = clock.reading(fresh=True).city(real)
    if state.fast_forward_to is not None and action in ("pause", "resume", "speed", "fastForward", "catchUp"):
        raise ValidationError({"action": ["Wait for the fast-forward to finish."]})
    message = ""
    if action == "pause":
        state.paused, state.anchor_city, state.anchor_real = True, city, real
        message = "Paused the city clock."
    elif action == "resume":
        state.paused, state.anchor_city, state.anchor_real = False, city, real
        message = "Resumed the city clock."
    elif action == "speed":
        try:
            speed = float(value)
        except (TypeError, ValueError):
            speed = None
        if speed not in SPEEDS:
            raise ValidationError({"value": [f"Speed must be one of {', '.join(f'{s:g}' for s in SPEEDS)}."]})
        state.speed, state.anchor_city, state.anchor_real = speed, city, real
        message = "Back to real time (1×)." if speed == 1 else f"City clock at {speed:g}× real time."
    elif action in ("fastForward", "catchUp"):
        if action == "catchUp":
            if city >= real - timedelta(minutes=1):
                raise ValidationError({"action": ["The city clock isn't behind the real one."]})
            to, label = real, "the real time"
        else:
            if value not in FAST_FORWARD_MINUTES:
                raise ValidationError(
                    {"value": [f"Fast-forward by one of: {', '.join(FAST_FORWARD_MINUTES)}."]}
                )
            to = city + timedelta(minutes=FAST_FORWARD_MINUTES[value])
            label = timezone.localtime(to).strftime("%a %d %b %H:%M")
        state.anchor_city, state.anchor_real = city, real
        state.fast_forward_from, state.fast_forward_to = city, to
        state.progress = min(state.progress, city)
        message = f"Fast-forwarding to {label}."
    elif action == "scenario":
        if value not in PROFILES:
            raise ValidationError({"value": [f"Scenario must be one of: {', '.join(PROFILES)}."]})
        state.scenario = value
        message = f"Scenario: {PROFILES[value].label}."
    elif action == "massCasualty":
        if state.incident_until is not None:
            raise ValidationError({"action": ["A mass-casualty event is already under way."]})
        state.save()
        incident = engine.start_incident(state, city)
        state.refresh_from_db()
        message = f"Mass-casualty event set off; receiving: {', '.join(incident['hospitals'])}."
    elif action == "endIncident":
        if state.incident_until is None:
            raise ValidationError({"action": ["There is no mass-casualty event to end."]})
        state.incident_until = state.incident_lat = state.incident_lng = None
        message = "Ended the mass-casualty event."
    state.save()
    after = _fields(state)
    record(actor, f"simulation.{action}", state, before=before, after=after)
    if action != "massCasualty":
        events.log(city, f"control.{action}", message)
    transaction.on_commit(clock.forget)
    return state


def status() -> dict:
    """What the Simulation panel shows."""
    state = engine.state()
    reading = clock.reading(fresh=True)
    real = timezone.now()
    city = reading.city(real)
    fast_forward = None
    if state.fast_forward_to is not None and state.fast_forward_from is not None:
        span = (state.fast_forward_to - state.fast_forward_from).total_seconds() or 1
        done = (state.progress - state.fast_forward_from).total_seconds()
        fast_forward = {
            "from": state.fast_forward_from,
            "to": state.fast_forward_to,
            "progress": state.progress,
            "percent": max(0, min(100, round(done / span * 100))),
        }
    incident = None
    if state.incident_until is not None:
        names = [
            s.hospital.name
            for s in engine.nearest(engine.build_sites(), state.incident_lat, state.incident_lng)
        ]
        incident = {"until": state.incident_until, "hospitals": names}
    recent = SimEvent.objects.select_related("hospital")[:50]
    return {
        "enabled": state.enabled,
        "mode": reading.mode,
        "paused": state.paused,
        "speed": state.speed,
        "speeds": SPEEDS,
        "cityTime": city,
        "realTime": real,
        "aheadMinutes": round((city - real).total_seconds() / 60),
        "engineAt": state.progress,
        "scenario": state.scenario,
        "scenarios": [{"value": k, "label": p.label} for k, p in PROFILES.items()],
        "fastForwardOptions": list(FAST_FORWARD_MINUTES),
        "fastForward": fast_forward,
        "incident": incident,
        "events": [
            {
                "id": e.pk,
                "at": e.at,
                "kind": e.kind,
                "message": e.message,
                "hospital": e.hospital.name if e.hospital else None,
            }
            for e in recent
        ],
    }
