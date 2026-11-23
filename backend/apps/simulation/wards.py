"""Wards, five minutes at a time (B21): beds are cleaned and made ready, patients due home leave (mostly late
morning), and planned admissions keep each ward near the occupancy the scenario runs at."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.emergencies.visits import initials
from apps.hospitals.models import Bed, BedStatus, BedType
from apps.hospitals.services import place_patient, vacate_bed
from apps.resources.services import change_status
from apps.resources.state_machine import TransitionNotAllowed

from .ed import STAY_DAYS
from .world import Site, stable

CLEANING_MINUTES = {BedType.EMERGENCY: (10, 30)}
WARD_CLEANING = (30, 90)
DISCHARGE_HOURS = (9, 17)  # wards send patients home between 09:00 and 17:00, most before 14:00
ADMISSION_HOURS = (10, 21)


def cleaning_done_at(bed: Bed):
    lo, hi = CLEANING_MINUTES.get(bed.bed_type, WARD_CLEANING)
    return bed.status_since + timedelta(
        minutes=stable("clean", bed.pk, bed.status_since.isoformat()).uniform(lo, hi)
    )


def cleaning_step(tick, end, held_beds: set[int], hospitals) -> None:
    """Beds whose cleaning time has passed are ready again, across the network."""
    for bed in Bed.objects.filter(hospital__in=hospitals, status=BedStatus.CLEANING).exclude(
        pk__in=held_beds
    ):
        if cleaning_done_at(bed) <= end:
            with transaction.atomic():
                locked = Bed.objects.select_for_update().get(pk=bed.pk)
                if locked.status == BedStatus.CLEANING:
                    change_status(locked, "markReady", actor=tick.actor, reason="Cleaned")


def _discharge_chance(local_hour: int, minutes: float) -> float:
    start, stop = DISCHARGE_HOURS
    if not start <= local_hour < stop:
        return 0.0
    hours_left = max(0.75, 14 - local_hour) if local_hour < 14 else 1.0
    return min(1.0, minutes / 60 / hours_left)


def step(site: Site, tick, start, end, held_beds: set[int]) -> None:
    rand = tick.rand
    minutes = (end - start).total_seconds() / 60
    local = timezone.localtime(end)
    today = local.date()
    ward_ids = list(site.wards)
    if not ward_ids:
        return

    # Patients due home go, as the day goes on. Only patients with a planned discharge date: a bed a nurse
    # admitted by hand has none, and the simulation leaves it alone.
    chance = _discharge_chance(local.hour, minutes)
    if chance:
        due = (
            Bed.objects.filter(ward_id__in=ward_ids, status=BedStatus.OCCUPIED, expected_discharge__lte=today)
            .exclude(pk__in=held_beds)
            .exclude(bed_type=BedType.EMERGENCY)
        )
        for bed in due:
            if rand.random() < chance:
                vacate_bed(bed, actor=tick.actor, reason="Discharged home")
                tick.count(site.hospital, "wards.discharges")

    # Planned admissions fill wards back towards the scenario's occupancy, in the afternoon and evening.
    if not ADMISSION_HOURS[0] <= local.hour < ADMISSION_HOURS[1]:
        return
    for ward_id, rule in site.wards.items():
        beds = Bed.objects.filter(ward_id=ward_id).exclude(status=BedStatus.OUT_OF_SERVICE)
        total = beds.count()
        if not total:
            continue
        taken = beds.filter(status__in=(BedStatus.OCCUPIED, BedStatus.RESERVED)).count()
        gap = tick.occupancy * total - taken
        if gap <= 0 or rand.random() >= min(0.6, gap * 0.012 * minutes):
            continue
        free = beds.filter(status=BedStatus.FREE).exclude(pk__in=held_beds).order_by("label").first()
        if free is None:
            continue
        lo, hi = STAY_DAYS.get(free.bed_type, STAY_DAYS[BedType.GENERAL])
        try:
            place_patient(
                free,
                initials=initials(rand),
                age=rand.randint(rule.lo, rule.hi),
                sex="F" if rule.female_only else rand.choice("FM"),
                actor=tick.actor,
                expected_discharge=today + timedelta(days=max(1, round(rand.uniform(lo, hi) * tick.stay))),
            )
            tick.count(site.hospital, "wards.admissions")
        except TransitionNotAllowed:
            continue
