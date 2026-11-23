"""The emergency department, five minutes at a time (B21): arrivals, treatment in triage order, patients
leaving, admitted patients waiting for a ward bed, and the waiting time that follows."""

import random
from datetime import timedelta

from apps.core.seed.history import ARRIVAL_SHAPE, ARRIVAL_TOTAL, WEEKDAY
from apps.core.seed.resources import poisson
from apps.emergencies import department
from apps.emergencies.models import EmergencyStatus, ErStatus, ErVisit, VisitStatus
from apps.emergencies.visits import age_in, arrive, finish, start_treatment
from apps.emergencies.wait import (
    FAST_TRACK_PER_DAY,
    MEAN_TREATMENT_HOURS,
    Inputs,
    capacity_per_hour,
    estimate,
)
from apps.hospitals.models import Bed, BedStatus, BedType
from apps.hospitals.services import vacate_bed
from apps.resources.state_machine import TransitionNotAllowed
from apps.staffing.models import StaffRole
from apps.staffing.services import on_duty, rostered

from . import events
from .profiles import pick
from .world import Site, emergency_beds_free

SERIOUS = ("respiratory", "cardiac", "trauma", "neurological", "abdominal")
AGE_BANDS = {
    "general": {"0-4": 0.07, "5-17": 0.1, "18-39": 0.34, "40-64": 0.31, "65+": 0.18},
    "children": {"0-4": 0.45, "5-17": 0.55},
    "women": {"18-39": 0.75, "40-64": 0.25},
}
# Days a patient stays on a ward, by bed type, before the scenario's multiplier.
STAY_DAYS = {BedType.ICU: (2, 7), BedType.ISOLATION: (3, 8), BedType.NICU: (5, 20), BedType.GENERAL: (1, 6)}
SPEED_UP_AFTER_HOURS = 3  # an emergency bed with a patient from before the simulation empties within hours


def arrivals_mean(site: Site, at, multiplier: float, minutes: float) -> float:
    local = at.astimezone(_zone())
    per_hour = site.arrivals_per_day * ARRIVAL_SHAPE[local.hour] / ARRIVAL_TOTAL * WEEKDAY[local.weekday()]
    return per_hour * multiplier * minutes / 60


def _zone():
    from django.utils import timezone

    return timezone.get_current_timezone()


def new_patient(
    site: Site, rand: random.Random, tick, *, triage: int | None = None, complaint: str | None = None
):
    triage = triage or int(pick(rand, tick.triage))
    complaint = complaint or pick(rand, tick.complaints)
    if triage <= 2 and complaint == "minor":
        complaint = rand.choice(SERIOUS)
    band = pick(rand, AGE_BANDS[site.population])
    if site.population == "women":
        sex = "F"
        complaint = "obstetric" if rand.random() < 0.6 else complaint
    else:
        sex = rand.choice("FM")
    return triage, band, sex, complaint


def ward_bed_for(site: Site, visit: ErVisit, age: int, held: set[int], rand: random.Random) -> Bed | None:
    """A free ward bed the patient may go to: intensive care for most resuscitation cases, isolation for
    breathing problems when there is one, otherwise a general bed on a ward that takes their age and sex."""
    wanted = [BedType.GENERAL]
    if visit.triage == 1 and rand.random() < 0.6:
        wanted = [BedType.ICU, BedType.GENERAL]
    elif visit.complaint in ("respiratory", "infection"):
        wanted = [BedType.ISOLATION, BedType.GENERAL]
    wards = [pk for pk, rule in site.wards.items() if rule.fits(age, visit.sex)]
    free = list(
        Bed.objects.filter(
            hospital=site.hospital, ward_id__in=wards, bed_type__in=wanted, status=BedStatus.FREE
        )
        .exclude(pk__in=held)
        .values_list("pk", "bed_type")
    )
    for bed_type in wanted:
        options = [pk for pk, kind in free if kind == bed_type]
        if options:
            return Bed.objects.get(pk=rand.choice(options))
    return None


def stay_days(bed: Bed, rand: random.Random, multiplier: float) -> int:
    lo, hi = STAY_DAYS.get(bed.bed_type, STAY_DAYS[BedType.GENERAL])
    return max(1, round(rand.uniform(lo, hi) * multiplier))


def _patient_age(visit: ErVisit, rand: random.Random) -> int:
    if visit.bed_id and visit.bed.patient_age is not None:
        return visit.bed.patient_age
    return age_in(visit.age_band, rand)


def _admit_or_board(site, visit, tick, held, rand) -> str:
    age = _patient_age(visit, rand)
    ward_bed = ward_bed_for(site, visit, age, held, rand)
    if ward_bed is None:
        if visit.status == VisitStatus.TREATING:
            finish(visit, "board", actor=tick.actor, reason="No ward bed free")
            return "board"
        return "wait"
    finish(
        visit,
        "admit",
        actor=tick.actor,
        ward_bed=ward_bed,
        rand=rand,
        age=age,
        stay_days=stay_days(ward_bed, rand, tick.stay),
    )
    return "admit"


def step(site: Site, tick, start, end, held_beds: set[int]) -> None:
    """One step of the hospital's emergency department, from `start` to `end` (city time)."""
    if not site.er_beds:
        return
    rand = tick.rand
    minutes = (end - start).total_seconds() / 60
    hospital = site.hospital

    # Arrivals, in random order and priority; during a mass-casualty event, trauma waves on top.
    usual = poisson(rand, arrivals_mean(site, end, tick.arrivals, minutes))
    incident = poisson(rand, tick.surge.get(hospital.pk, 0.0) * minutes / 60)
    for n in range(usual + incident):
        if n >= usual:
            patient = new_patient(
                site, rand, tick, triage=int(pick(rand, tick.incident_triage)), complaint="trauma"
            )
        else:
            patient = new_patient(site, rand, tick)
        triage, band, sex, complaint = patient
        visit = arrive(
            hospital=hospital,
            triage=triage,
            age_band=band,
            sex=sex,
            complaint=complaint,
            actor=tick.actor,
            rand=rand,
        )
        tick.count(hospital, "er.arrivals")
        if triage == 1:
            events.log(
                end,
                "er.resuscitation",
                f"{hospital.name}: a triage 1 patient arrived ({visit.tag}).",
                hospital,
            )
            events.alert(
                tick.state,
                at=end,
                kind="resuscitation",
                hospital=hospital,
                module="emergencies",
                message=f"Triage 1 patient {visit.tag} has arrived in the emergency department.",
                link="/staff/emergencies#department",
                actor=tick.actor,
            )

    # Treatment that has run its course ends: home, a ward, or another hospital.
    for visit in ErVisit.objects.filter(
        hospital=hospital, status=VisitStatus.TREATING, due_at__lte=end, handled_by=None
    ).select_related("bed"):
        roll = rand.random()
        admit = tick.admit.get(visit.triage, 0.1)
        if roll < admit:
            _admit_or_board(site, visit, tick, held_beds, rand)
        elif roll < admit + tick.transfer:
            finish(visit, "transfer", actor=tick.actor, reason="Needs a service this hospital doesn't have")
        else:
            finish(visit, "discharge", actor=tick.actor)
        tick.count(hospital, "er.departures")

    # Admitted patients still in the department go up when a ward bed frees.
    for visit in ErVisit.objects.filter(
        hospital=hospital, status=VisitStatus.BOARDING, handled_by=None
    ).select_related("bed"):
        if _admit_or_board(site, visit, tick, held_beds, rand) != "admit":
            break

    # Some of the least urgent give up after an hour.
    hour_ago = end - timedelta(hours=1)
    for visit in ErVisit.objects.filter(
        hospital=hospital, status=VisitStatus.WAITING, triage__gte=4, arrived_at__lte=hour_ago
    ):
        if rand.random() < tick.leave_unseen * minutes / 60:
            finish(visit, "leaveUnseen", actor=tick.actor)
            tick.count(hospital, "er.departures")

    # Patients are seen in triage order, as far as doctors and beds allow. Triage 1 is seen at once.
    inputs = inputs_for(site, end, held_beds)
    places = round(capacity_per_hour(inputs) * MEAN_TREATMENT_HOURS) - (
        ErVisit.objects.filter(hospital=hospital, status=VisitStatus.TREATING).count()
    )
    free_beds = list(emergency_beds_free(site, held_beds))
    # Minor complaints (4-5) can also go to the fast track: a nurse practitioner sees them in a chair.
    fast_track = max(1, round(site.arrivals_per_day / FAST_TRACK_PER_DAY)) - (
        ErVisit.objects.filter(
            hospital=hospital, status=VisitStatus.TREATING, bed=None, triage__gte=4
        ).count()
    )
    for visit in ErVisit.objects.filter(hospital=hospital, status=VisitStatus.WAITING).order_by(
        "triage", "arrived_at"
    ):
        minor = visit.triage >= 4
        fast = places <= 0 and minor and fast_track > 0
        if places <= 0 and visit.triage > 1 and not fast:
            if minor:
                break
            continue  # nobody free for this one; a minor complaint behind it may still go to the fast track
        needs_bed = not fast and (visit.triage <= 3 or rand.random() < 0.35)
        if needs_bed and not free_beds:
            if not minor:
                continue  # waits for a bed
            needs_bed = False  # a minor complaint can be seen in a chair
        bed = free_beds.pop(0) if needs_bed else None
        lo, hi = tick.treatment[visit.triage]
        try:
            start_treatment(visit, bed=bed, minutes=rand.uniform(lo, hi), actor=tick.actor, rand=rand)
        except TransitionNotAllowed:
            continue  # the bed was taken a moment ago
        if fast:
            fast_track -= 1
        else:
            places -= 1

    # Patients in emergency beds from before the simulation started go home or up within a few hours.
    in_visit = ErVisit.objects.filter(
        hospital=hospital, status__in=(VisitStatus.TREATING, VisitStatus.BOARDING)
    ).values("bed_id")
    old = (
        Bed.objects.filter(hospital=hospital, bed_type=BedType.EMERGENCY, status=BedStatus.OCCUPIED)
        .exclude(pk__in=in_visit)
        .exclude(pk__in=held_beds)
    )
    for bed in old:
        if rand.random() < minutes / 60 / SPEED_UP_AFTER_HOURS:
            vacate_bed(bed, actor=tick.actor, reason="Patient discharged")
            tick.count(hospital, "er.departures")

    publish_wait(site, tick, end, held_beds)


def inputs_for(site: Site, at, held_beds=frozenset()) -> Inputs:
    hospital = site.hospital
    waiting = {}
    for level in ErVisit.objects.filter(hospital=hospital, status=VisitStatus.WAITING).values_list(
        "triage", flat=True
    ):
        waiting[level] = waiting.get(level, 0) + 1
    staff = on_duty(hospital, at, department=site.er_department)
    planned = rostered(hospital, at, department=site.er_department)
    beds = Bed.objects.filter(hospital=hospital, bed_type=BedType.EMERGENCY).exclude(
        status=BedStatus.OUT_OF_SERVICE
    )
    return Inputs(
        waiting=waiting,
        doctors=staff[StaffRole.DOCTOR],
        doctors_rostered=planned[StaffRole.DOCTOR],
        nurses=staff[StaffRole.NURSE],
        nurses_rostered=planned[StaffRole.NURSE],
        beds=beds.count(),
        beds_free=beds.filter(status=BedStatus.FREE).exclude(pk__in=held_beds).count(),
        boarding=ErVisit.objects.filter(hospital=hospital, status=VisitStatus.BOARDING).count(),
        arrivals_last_hour=ErVisit.objects.filter(
            hospital=hospital, arrived_at__gt=at - timedelta(hours=1)
        ).count(),
        usual_per_day=site.arrivals_per_day,
    )


PERSON_HOLD = timedelta(minutes=30)


def publish_wait(site: Site, tick, at, held_beds=frozenset(), result=None) -> None:
    """Set the hospital's public status from the estimate, unless a person set it in the last half hour."""
    current = EmergencyStatus.objects.filter(hospital=site.hospital).first()
    if current and current.set_by_id not in (None, tick.actor.pk) and at - current.updated_at < PERSON_HOLD:
        return
    result = result or estimate(inputs_for(site, at, held_beds))
    before = current.status if current else None
    department.update_department_status(
        hospital=site.hospital,
        status=result.status,
        wait_minutes=result.minutes,
        waiting_count=result.waiting,
        actor=tick.actor,
        log_minor=False,
        factors=result.factors,
    )
    if result.status != before and result.status == ErStatus.DIVERTING:
        events.log(at, "er.diverting", f"{site.hospital.name} is not accepting ambulances.", site.hospital)
        events.alert(
            tick.state,
            at=at,
            kind="diverting",
            hospital=site.hospital,
            module="emergencies",
            message="The emergency department is not accepting ambulances: "
            f"{result.waiting} waiting, about {result.minutes} minutes.",
            link="/staff/emergencies#department",
            actor=tick.actor,
        )
    elif before == ErStatus.DIVERTING and result.status != before:
        events.log(at, "er.accepting", f"{site.hospital.name} is accepting ambulances again.", site.hospital)
