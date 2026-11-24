"""Blood, five minutes at a time (B21): units are issued through the day (oldest expiry first), donations
come in as quarantined units during clinic hours, pass their screening tests a few hours later (about 1 in 50
fails one and is discarded), and units past their date expire. Demo stock is never touched."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.blood.models import REQUIRED_TESTS, BloodUnit, Component, UnitStatus
from apps.blood.services import expire_overdue_units, receive_donation, record_test
from apps.core.seed.history import BLOOD_SHAPE
from apps.core.seed.resources import poisson
from apps.hospitals.models import StorageLocation
from apps.resources.services import change_status

from . import events
from .profiles import pick
from .world import Site, stable

GROUP_SHARE = {
    "B+": 0.33,
    "O+": 0.28,
    "A+": 0.22,
    "AB+": 0.07,
    "B-": 0.03,
    "O-": 0.025,
    "A-": 0.025,
    "AB-": 0.02,
}
ISSUE_MIX = {Component.RED_CELLS: 0.6, Component.PLASMA: 0.25, Component.PLATELETS: 0.15}
# What one donation gives: red cells always, plasma from half (the rest goes to fractionation), platelets
# from a third (they keep five days). Donations at 60% of the units used a day (world.py) keep stock steady.
PLASMA_SHARE, PLATELET_SHARE = 0.5, 0.35
SHELF_DAYS = {Component.RED_CELLS: 42, Component.PLASMA: 365, Component.PLATELETS: 5}
CLINIC_HOURS = (9, 19)
SCREENING_HOURS = (3, 6)
FAIL_SHARE = 0.02
FACILITY = "G7799"  # the simulation's donation numbers, apart from the seed's G7731


def _usable(hospital, group, component, now):
    return BloodUnit.objects.filter(
        hospital=hospital,
        group=group,
        component=component,
        status=UnitStatus.AVAILABLE,
        expires_at__gt=now,
        demo_stock=False,
    )


def _demo_groups(hospital) -> set:
    """(group, component) pairs the demo relies on at this hospital: the simulation neither uses nor adds to
    them, so the scripted shortage stays as the script says."""
    return set(
        BloodUnit.objects.filter(hospital=hospital, demo_stock=True)
        .values_list("group", "component")
        .distinct()
    )


def issue(site: Site, tick, end, group, component, held: set[int]) -> bool:
    with transaction.atomic():
        unit = (
            _usable(site.hospital, group, component, end)
            .exclude(pk__in=held)
            .select_for_update(skip_locked=True)
            .order_by("expires_at", "pk")
            .first()
        )
        if unit is None:
            return False
        change_status(unit, "issue", actor=tick.actor, reason="Transfused")
    tick.count(site.hospital, "blood.issued")
    if component == Component.RED_CELLS and not _usable(site.hospital, group, component, end).exists():
        label = f"{group} red cells"
        events.log(end, "blood.zero", f"{site.hospital.name} has no {label} left.", site.hospital)
        events.alert(
            tick.state,
            at=end,
            kind=f"blood_zero_{group}",
            hospital=site.hospital,
            module="blood",
            message=f"No usable {label} left in stock. Request a transfer or call donors.",
            link="/staff/blood",
            actor=tick.actor,
        )
    return True


def _next_number(tick) -> str:
    year = timezone.localdate(tick.end).strftime("%y")
    if tick.donation_seq is None:
        last = (
            BloodUnit.objects.filter(donation_number__startswith=f"{FACILITY} {year} ")
            .order_by("-donation_number")
            .values_list("donation_number", flat=True)
            .first()
        )
        tick.donation_seq = int(last.rsplit(" ", 1)[1]) if last else 0
    tick.donation_seq += 1
    return f"{FACILITY} {year} {tick.donation_seq:06d}"


def _fridge(hospital, component):
    wanted = {Component.PLASMA: "Plasma freezer", Component.PLATELETS: "Platelet agitator"}.get(
        component, "fridge"
    )
    locations = list(StorageLocation.objects.filter(hospital=hospital))
    return next((loc for loc in locations if wanted.lower() in loc.name.lower()), None) or next(
        (loc for loc in locations if "fridge" in loc.name.lower()), locations[0] if locations else None
    )


def components(rand) -> list[str]:
    """The units one donation is split into."""
    made = [Component.RED_CELLS]
    if rand.random() < PLASMA_SHARE:
        made.append(Component.PLASMA)
    if rand.random() < PLATELET_SHARE:
        made.append(Component.PLATELETS)
    return made


def donate(site: Site, tick, at, group, skip: set) -> int:
    """One donation, split into its components. Returns units made."""
    rand = tick.rand
    made = 0
    for component in components(rand):
        if (group, component) in skip:
            continue
        receive_donation(
            hospital=site.hospital,
            group=group,
            component=component,
            donation_number=_next_number(tick),
            collected_at=at,
            shelf_days=SHELF_DAYS[component],
            storage_location=_fridge(site.hospital, component),
            actor=tick.actor,
        )
        made += 1
    tick.count(site.hospital, "blood.donated")
    return made


def screen(site: Site, tick, end) -> None:
    """Quarantined units whose tests are due get their results: all pass, or one fails and the unit goes."""
    for unit in BloodUnit.objects.filter(
        hospital=site.hospital, status=UnitStatus.QUARANTINED, demo_stock=False
    ):
        rand = stable("screen", unit.pk)
        if unit.collected_at + timedelta(hours=rand.uniform(*SCREENING_HOURS)) > end:
            continue
        failing = rand.choice(REQUIRED_TESTS) if rand.random() < FAIL_SHARE else None
        done = set(unit.tests.values_list("test", flat=True))
        for test in REQUIRED_TESTS:
            if test in done:
                continue
            passed = test != failing
            record_test(
                unit.donation_number,
                test=test,
                passed=passed,
                reason="" if passed else "Reactive on screening",
                actor=tick.actor,
            )
            if not passed:
                break


def step(site: Site, tick, start, end, held: set[int]) -> None:
    if not site.blood_per_day and not site.donations_per_day:
        return
    rand = tick.rand
    minutes = (end - start).total_seconds() / 60
    local = timezone.localtime(end)
    skip = _demo_groups(site.hospital)

    use = (
        site.blood_per_day * tick.blood_use * BLOOD_SHAPE[local.hour] / sum(BLOOD_SHAPE) * 24 * minutes / 1440
    )
    for _ in range(poisson(rand, use)):
        component = pick(rand, ISSUE_MIX)
        group = pick(rand, GROUP_SHARE)
        if (group, component) not in skip:
            issue(site, tick, end, group, component, held)
    surge = tick.blood_surge.get(site.hospital.pk, 0.0)
    for _ in range(poisson(rand, surge * minutes / 60)):  # a mass-casualty event: O groups, red cells
        group = "O-" if rand.random() < 0.4 else "O+"
        if (group, Component.RED_CELLS) not in skip:
            issue(site, tick, end, group, Component.RED_CELLS, held)

    if CLINIC_HOURS[0] <= local.hour < CLINIC_HOURS[1] and site.donations_per_day:
        hours_open = CLINIC_HOURS[1] - CLINIC_HOURS[0]
        rate = site.donations_per_day * tick.donations / hours_open * minutes / 60
        for _ in range(poisson(rand, rate)):
            donate(
                site, tick, end - timedelta(minutes=rand.uniform(0, minutes)), pick(rand, GROUP_SHARE), skip
            )
    screen(site, tick, end)


def expire(end) -> int:
    return expire_overdue_units(end)
