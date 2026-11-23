"""New emergency cases and delays (B21). Now and then a hospital opens a case for blood, a bed, equipment or a
theatre it can't cover, through the same service staff use, so matching, holds and transfers all work on it.
A case nobody picks up is met locally after a while and cancelled by the simulation; once a person acts on a
case it is theirs, and the simulation never touches it again. Ambulance trips under way are sometimes held up,
which moves their arrival time."""

from datetime import timedelta

from apps.ambulances.models import Trip, TripStatus
from apps.audit.services import record
from apps.core.seed.resources import poisson
from apps.emergencies.models import EmergencyRequest, PatientTransfer, RequestStatus, Severity
from apps.emergencies.services import apply_case_action, create_case
from apps.matching.models import Reservation
from apps.transfers.models import Transfer

from . import events
from .blood import GROUP_SHARE
from .profiles import pick
from .world import stable

SEVERITY = {Severity.CRITICAL: 0.25, Severity.HIGH: 0.4, Severity.MODERATE: 0.25, Severity.LOW: 0.1}
NEEDS = {"blood": 0.55, "bed": 0.25, "equipment": 0.12, "operatingRoom": 0.08}
UNTOUCHED_MINUTES = (60, 180)  # a case nobody picks up is met locally within this
MAX_TRIP_ETA = 240


def _need(rand, kind: str) -> dict:
    if kind == "blood":
        return {
            "type": "blood",
            "group": pick(rand, GROUP_SHARE),
            "component": "redCells" if rand.random() < 0.8 else "platelets",
            "quantity": rand.randint(2, 6),
        }
    if kind == "bed":
        return {"type": "bed", "bedType": rand.choice(["icu", "icu", "isolation", "nicu"]), "quantity": 1}
    if kind == "equipment":
        return {"type": "equipment", "equipmentType": rand.choice(["ventilator", "dialysis"]), "quantity": 1}
    return {"type": "operatingRoom", "capability": rand.choice(["trauma", "cardiac", "neuro"]), "quantity": 1}


def open_cases(sites, tick, start, end) -> None:
    rand = tick.rand
    minutes = (end - start).total_seconds() / 60
    with_ed = [s for s in sites if s.er_beds]
    if not with_ed:
        return
    count = poisson(rand, tick.cases / 1440 * minutes)
    incident = poisson(rand, tick.case_surge * minutes / 60)
    for n in range(count + incident):
        if n >= count and tick.receivers:
            site = rand.choice([s for s in with_ed if s.hospital.pk in tick.receivers] or with_ed)
            severity = Severity.CRITICAL
        else:
            site = rand.choices(with_ed, weights=[s.arrivals_per_day for s in with_ed])[0]
            severity = pick(rand, SEVERITY)
        kinds = [pick(rand, NEEDS)]
        if rand.random() < 0.25:
            kinds.append(pick(rand, NEEDS))
        items = [_need(rand, kind) for kind in dict.fromkeys(kinds)]
        case = create_case(
            severity=severity,
            patient_ref=f"SIM-{rand.randint(100000, 999999)}",
            items=items,
            actor=tick.actor,
            hospital=site.hospital,
        )
        events.log(
            end,
            "case.opened",
            f"{site.hospital.name} opened {severity} case {case.reference}.",
            site.hospital,
        )


def touched_by_people(case: EmergencyRequest, actor) -> bool:
    """Has anyone but the simulation acted on this case?"""
    return (
        case.history.exclude(actor=actor).exists()
        or Reservation.objects.filter(request_item__request=case).exists()
        or Transfer.objects.filter(request_item__request=case).exists()
        or PatientTransfer.objects.filter(request=case).exists()
    )


def resolve_untouched(tick, end) -> None:
    """The simulation's own open cases that nobody picked up are met locally and cancelled."""
    for case in EmergencyRequest.objects.filter(created_by=tick.actor, status=RequestStatus.OPEN):
        wait = timedelta(minutes=stable("case", case.pk).uniform(*UNTOUCHED_MINUTES))
        if case.created_at + wait > end or touched_by_people(case, tick.actor):
            continue
        apply_case_action(
            case.reference, "cancel", note="Met from the hospital's own stock (simulation).", actor=tick.actor
        )


def delay_trips(tick, start, end) -> None:
    minutes = (end - start).total_seconds() / 60
    for trip in Trip.objects.filter(status__in=(TripStatus.DISPATCHED, TripStatus.EN_ROUTE)).select_related(
        "ambulance__hospital"
    ):
        if tick.rand.random() >= tick.trip_delay * minutes / 5 or trip.eta_minutes >= MAX_TRIP_ETA:
            continue
        before = trip.eta_minutes
        trip.eta_minutes = min(MAX_TRIP_ETA, before + tick.rand.randint(5, 15))
        trip.save(update_fields=["eta_minutes"])
        record(
            tick.actor,
            "trip.delayed",
            trip,
            before={"etaMinutes": before},
            after={"etaMinutes": trip.eta_minutes},
            reason="Held up in traffic",
        )
        events.log(
            end,
            "trip.delayed",
            f"Ambulance {trip.ambulance.identifier} is held up: now {trip.eta_minutes} minutes.",
            trip.ambulance.hospital,
        )
