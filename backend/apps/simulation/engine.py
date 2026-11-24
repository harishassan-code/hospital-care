"""The simulation's tick (B21): bring the city from where the engine got to (`progress`) up to the city clock,
in five-minute steps for the last two hours and hour by hour before that (a fast-forward, or a site nobody had
open for a while). One tick at a time across every copy of the app (a lease on the state row); each step is
its own small transactions, so a person's action never waits long for it.

Rates are drawn afresh on every tick from the scenario's ranges (profiles.py), so no two days are alike."""

import math
import random
import time as _time
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.audit.services import record
from apps.blood.models import BloodUnit
from apps.core import clock
from apps.core.seed.history import ARRIVAL_SHAPE
from apps.core.seed.resources import poisson
from apps.emergencies.models import ErVisit
from apps.hospitals.models import Bed
from apps.metrics import catalog
from apps.metrics import services as metrics
from apps.metrics.models import MetricSnapshot
from apps.operating_rooms.models import OperatingRoom
from apps.resources.services import held_ids
from apps.staffing.models import Shift
from apps.staffing.services import extend_rota

from . import blood, cases, ed, events, staff, theatres, wards
from .actor import system_user
from .coarse import coarse_hour
from .models import SimEvent, SimulationState
from .profiles import INCIDENT_SITES, MASS_CASUALTY, PROFILES, draw, shares
from .world import build_sites

STEP = timedelta(minutes=5)
DETAIL = timedelta(hours=2)  # the last two hours of any catch-up run step by step
KEEP = timedelta(days=14)  # visits, events and snapshots older than this are pruned; a longer gap is skipped
MIN_INTERVAL = timedelta(seconds=15)  # at most one tick every 15 real seconds, unless forced
LEASE = timedelta(seconds=60)
BUDGET_SECONDS = 6.0  # a tick stops after about this long; the next one carries on


def state() -> SimulationState:
    current = SimulationState.objects.filter(pk=1).first()
    if current is None:
        now = timezone.now()
        current, _ = SimulationState.objects.get_or_create(
            pk=1, defaults={"anchor_real": now, "anchor_city": now, "progress": now}
        )
    return current


@dataclass
class Tick:
    """One tick's draws from the scenario, and its running counts."""

    state: SimulationState
    actor: object
    rand: random.Random
    arrivals: float = 1.0
    triage: dict = field(default_factory=dict)
    complaints: dict = field(default_factory=dict)
    admit: dict = field(default_factory=dict)
    transfer: float = 0.0
    leave_unseen: float = 0.0
    treatment: dict = field(default_factory=dict)
    stay: float = 1.0
    occupancy: float = 0.85
    blood_use: float = 1.0
    donations: float = 1.0
    cancel: float = 0.1
    list_fill: float = 0.8
    emergency_theatre: float = 0.2
    absent: float = 0.02
    late: float = 0.05
    cases: float = 3.0
    trip_delay: float = 0.03
    # A mass-casualty event, while it lasts: extra arrivals, red-cell use and theatre cases per hour at the
    # receiving hospitals, and extra cases across them.
    receivers: tuple = ()
    surge: dict = field(default_factory=dict)
    incident_triage: dict = field(default_factory=dict)
    blood_surge: dict = field(default_factory=dict)
    theatre_surge: dict = field(default_factory=dict)
    case_surge: float = 0.0
    end: datetime | None = None
    donation_seq: int | None = None
    absent_now: dict = field(default_factory=dict)

    def count(self, hospital, key: str, n: int = 1) -> None:
        bucket = self.state.counters.setdefault(str(hospital.pk), {})
        bucket[key] = bucket.get(key, 0) + n

    def count_absent(self, hospital_id: int) -> None:
        self.absent_now[hospital_id] = self.absent_now.get(hospital_id, 0) + 1


def make_tick(current: SimulationState, sites) -> Tick:
    rand = random.Random()
    profile = PROFILES.get(current.scenario, PROFILES["regular"])
    tick = Tick(
        state=current,
        actor=system_user(),
        rand=rand,
        arrivals=draw(rand, profile.arrivals),
        triage=shares(rand, profile.triage),
        complaints=shares(rand, profile.complaints),
        admit=profile.admit,
        transfer=draw(rand, profile.transfer),
        leave_unseen=draw(rand, profile.leave_unseen),
        treatment=profile.treatment_minutes,
        stay=draw(rand, profile.stay),
        occupancy=draw(rand, profile.occupancy),
        blood_use=draw(rand, profile.blood_use),
        donations=draw(rand, profile.donations),
        cancel=draw(rand, profile.cancel),
        list_fill=0.6 if current.scenario == "slow" else 0.8,
        emergency_theatre=draw(rand, profile.emergency_theatre),
        absent=draw(rand, profile.absent),
        late=draw(rand, profile.late),
        cases=draw(rand, profile.cases),
        trip_delay=draw(rand, profile.trip_delay),
    )
    if current.incident_until is not None and current.incident_lat is not None:
        receivers = nearest(sites, current.incident_lat, current.incident_lng)
        mc = MASS_CASUALTY
        tick.receivers = tuple(s.hospital.pk for s in receivers)
        tick.incident_triage = shares(rand, mc.triage)
        for rank, site in enumerate(receivers):  # the nearest takes the most
            weight = 1.0 / (1 + rank * 0.5)
            tick.surge[site.hospital.pk] = draw(rand, mc.per_hospital_per_hour) * weight
            tick.blood_surge[site.hospital.pk] = site.blood_per_day / 24 * draw(rand, mc.blood_use) * weight
            tick.theatre_surge[site.hospital.pk] = draw(rand, mc.emergency_theatre_per_hour) * weight
        tick.case_surge = draw(rand, mc.cases)
    return tick


def distance_km(lat1, lng1, lat2, lng2) -> float:
    rad = math.radians
    a = (
        math.sin(rad(lat2 - lat1) / 2) ** 2
        + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(rad(lng2 - lng1) / 2) ** 2
    )
    return 6371 * 2 * math.asin(math.sqrt(a))


def nearest(sites, lat, lng):
    """The emergency departments a mass-casualty event sends patients to: the nearest general ones (a
    children's or women's hospital takes its own patients, not a trauma wave)."""
    with_ed = [s for s in sites if s.er_beds and s.population == "general"] or [s for s in sites if s.er_beds]
    with_ed.sort(key=lambda s: distance_km(lat, lng, float(s.hospital.latitude), float(s.hospital.longitude)))
    return with_ed[: MASS_CASUALTY.hospitals]


# ── One step, one hour, one day ──────────────────────────────────────────────────────────────────────


def detailed_step(tick: Tick, sites, start: datetime, end: datetime) -> None:
    """Everything that happens in the city between `start` and `end` (about five minutes), event by event."""
    tick.end = end
    hospitals = [s.hospital for s in sites]
    with clock.at(end):
        held_beds, held_rooms, held_units = held_ids(Bed), held_ids(OperatingRoom), held_ids(BloodUnit)
        staff.step(tick, start, end, hospitals)
        wards.cleaning_step(tick, end, held_beds, hospitals)
        for site in sites:
            ed.step(site, tick, start, end, held_beds)
            wards.step(site, tick, start, end, held_beds)
            blood.step(site, tick, start, end, held_units)
            theatres.step(site, tick, start, end, held_rooms)
        blood.expire(end)
        cases.open_cases(sites, tick, start, end)
        cases.resolve_untouched(tick, end)
        cases.delay_trips(tick, start, end)
        for hospital_id, n in tick.absent_now.items():
            hospital = next(s.hospital for s in sites if s.hospital.pk == hospital_id)
            events.log(end, "staff.absent", f"{hospital.name}: {n} on the rota didn't come in.", hospital)
        tick.absent_now.clear()


def hour_end(tick: Tick, sites, hour_start: datetime, rand=None) -> None:
    """Write the hour's figures for every hospital: levels now, and the counts kept during the hour."""
    rand = rand or tick.rand
    at = hour_start + timedelta(hours=1)
    for site in sites:
        values = metrics.levels(site.hospital, at)
        bucket = tick.state.counters.pop(str(site.hospital.pk), {})
        for key in catalog.COUNTS:
            if key == catalog.AMBULANCE_TRIPS:
                fleet = metrics.has_fleet(site.hospital)
                if fleet:
                    local = timezone.localtime(hour_start)
                    values[key] = poisson(rand, fleet * 0.12 * ARRIVAL_SHAPE[local.hour])
                continue
            if key in bucket or (key.startswith("er.") and site.er_beds):
                values[key] = bucket.get(key, 0)
            elif key.startswith("blood.") and (site.blood_per_day or site.donations_per_day):
                values[key] = bucket.get(key, 0)
        metrics.write_hour(site.hospital, hour_start, values)


def new_day(tick: Tick, sites, day) -> None:
    """Once per city day: rotas and on-call stay a week ahead, tomorrow's theatre lists are booked, and data
    older than two weeks goes."""
    from apps.core.seed.staffing import _top_up_windows

    extend_rota(day)
    for site in sites:
        _top_up_windows(site.hospital, day, 7)
        theatres.book_lists(site, tick, day + timedelta(days=1))
    prune(timezone.make_aware(datetime.combine(day, datetime.min.time())))


def prune(now: datetime) -> None:
    cutoff = now - KEEP
    ErVisit.objects.filter(arrived_at__lt=cutoff).exclude(
        status__in=("waiting", "treating", "boarding")
    ).delete()
    SimEvent.objects.filter(at__lt=cutoff).delete()
    MetricSnapshot.objects.filter(at__lt=cutoff).delete()
    Shift.objects.filter(ends_at__lt=cutoff - timedelta(days=7)).delete()


# ── The tick ─────────────────────────────────────────────────────────────────────────────────────────


def _take_lease(real: datetime) -> bool:
    return bool(
        SimulationState.objects.filter(pk=1)
        .filter(Q(lease_until__isnull=True) | Q(lease_until__lt=real))
        .update(lease_until=real + LEASE)
    )


def _save(current: SimulationState, **fields) -> None:
    for name, value in fields.items():
        setattr(current, name, value)
    SimulationState.objects.filter(pk=1).update(
        progress=current.progress,
        counters=current.counters,
        alerts_sent=current.alerts_sent,
        **fields,
    )


def run(*, force: bool = False, budget: float = BUDGET_SECONDS) -> dict:
    """Run the simulation up to the city clock, within `budget` seconds. Returns where it got to."""
    if not settings.SIMULATION_ENABLED:
        return {"ran": False, "reason": "off"}
    real = timezone.now()
    current = state()
    if not current.enabled:
        return {"ran": False, "reason": "off"}
    reading = clock.reading(fresh=True)
    fast_forward = current.fast_forward_to is not None
    if current.paused and not fast_forward:
        return {"ran": False, "reason": "paused"}
    if (
        not force
        and not fast_forward
        and current.last_tick_real
        and real - current.last_tick_real < MIN_INTERVAL
    ):
        return {"ran": False, "reason": "tooSoon"}
    if not _take_lease(real):
        return {"ran": False, "reason": "busy"}
    started = _time.monotonic()
    try:
        current.refresh_from_db()
        target = current.fast_forward_to or reading.city(real)
        progress = current.progress
        if target - progress > KEEP:
            progress = target - KEEP  # nothing older is kept anyway
        sites = build_sites()
        tick = make_tick(current, sites)
        coarse = {"hours": 0}
        while progress < target and _time.monotonic() - started < budget:
            local = timezone.localtime(progress)
            hour_start = local.replace(minute=0, second=0, microsecond=0)
            if target - progress > DETAIL:
                end = min(hour_start + timedelta(hours=1), target - DETAIL)
                with clock.at(end):
                    coarse_hour(tick, sites, progress, end, coarse)
            else:
                end = min(progress + STEP, hour_start + timedelta(hours=1), target)
                detailed_step(tick, sites, progress, end)
            end_local = timezone.localtime(end)
            if end_local.minute == 0 and end_local.second == 0 and end > progress:
                hour_end(tick, sites, end - timedelta(hours=1))
            if end_local.date() != local.date():
                with clock.at(end):
                    new_day(tick, sites, end_local.date())
            _end_incident(current, tick, end)
            progress = end
            current.progress = progress
            _save(current)
        if coarse["hours"]:
            record(
                tick.actor,
                "simulation.fast_forwarded",
                current,
                after={"hours": coarse["hours"], **{k: v for k, v in coarse.items() if k != "hours"}},
            )
        done = progress >= target
        if fast_forward and done:
            events.log(
                target, "clock.fastForward", f"Fast-forwarded to {timezone.localtime(target):%a %d %b %H:%M}."
            )
            _save(
                current,
                anchor_city=target,
                anchor_real=timezone.now(),
                fast_forward_to=None,
                fast_forward_from=None,
            )
        return {
            "ran": True,
            "progress": progress,
            "target": target,
            "behind": not done,
            "seconds": round(_time.monotonic() - started, 2),
        }
    finally:
        SimulationState.objects.filter(pk=1).update(lease_until=None, last_tick_real=real)
        clock.forget()


def _end_incident(current: SimulationState, tick: Tick, at: datetime) -> None:
    if current.incident_until is not None and at >= current.incident_until:
        events.log(
            at, "incident.over", "The mass-casualty event is over; the city settles back to its season."
        )
        current.incident_until = current.incident_lat = current.incident_lng = None
        _save(current, incident_until=None, incident_lat=None, incident_lng=None)
        tick.receivers, tick.surge, tick.blood_surge, tick.theatre_surge, tick.case_surge = (
            (),
            {},
            {},
            {},
            0.0,
        )


def start_incident(current: SimulationState, at: datetime, rand: random.Random | None = None) -> dict:
    rand = rand or random.Random()
    lat, lng = rand.choice(INCIDENT_SITES)
    lat, lng = lat + rand.uniform(-0.01, 0.01), lng + rand.uniform(-0.01, 0.01)
    until = at + timedelta(hours=draw(rand, MASS_CASUALTY.hours))
    names = [s.hospital.name for s in nearest(build_sites(), lat, lng)]
    with transaction.atomic():
        SimulationState.objects.filter(pk=1).update(incident_lat=lat, incident_lng=lng, incident_until=until)
    events.log(
        at,
        "incident.started",
        f"Mass-casualty event: patients are on their way to {', '.join(names)} until "
        f"{timezone.localtime(until):%H:%M}.",
    )
    return {"lat": lat, "lng": lng, "until": until, "hospitals": names}
