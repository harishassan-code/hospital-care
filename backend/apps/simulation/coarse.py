"""A fast-forward hour (B21): the same city, summarised. Instead of one patient at a time, each hour draws how
many arrived, were admitted, went home, gave or received blood, and sets beds, stock, rooms, rotas and the
waiting time to where that leaves them, in bulk, with one audit entry for the whole run (engine.run). Status
moves still go through each resource's state machine. The last two hours of a fast-forward run event by event,
so the city arrives at its new time with a live queue."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.blood.models import REQUIRED_TESTS, BloodUnit, TestResult, UnitStatus
from apps.core.seed.history import ARRIVAL_SHAPE, ARRIVAL_TOTAL, BLOOD_SHAPE, WEEKDAY
from apps.core.seed.resources import poisson
from apps.emergencies import department
from apps.emergencies.models import ErVisit, VisitOutcome, VisitStatus
from apps.emergencies.visits import TAG_LETTERS
from apps.emergencies.wait import MEAN_TREATMENT_HOURS, capacity_per_hour, er_status_for, er_wait_minutes
from apps.hospitals.models import BED_LIFECYCLE, Bed, BedStatus, BedType
from apps.operating_rooms.models import OR_LIFECYCLE, OperatingRoom, OrBooking, OrBookingStatus, OrStatus
from apps.resources.services import held_ids

from . import blood, cases, staff
from .ed import STAY_DAYS, inputs_for
from .profiles import pick
from .wards import ADMISSION_HOURS, _discharge_chance


def _walk(machine, status, *actions):
    for action in actions:
        status = machine.next(status, action)
    return status


def _letters(rand):
    return f"{rand.choice(TAG_LETTERS)}.{rand.choice(TAG_LETTERS)}."


def close_open_visits(at) -> int:
    """A fast-forward starts by letting today's emergency patients go: their beds are free again."""
    open_visits = ErVisit.objects.filter(
        status__in=(VisitStatus.WAITING, VisitStatus.TREATING, VisitStatus.BOARDING)
    )
    beds = list(open_visits.exclude(bed=None).values_list("bed_id", flat=True))
    count = open_visits.update(
        status=VisitStatus.LEFT, outcome=VisitOutcome.DISCHARGED, left_at=at, due_at=None
    )
    _free_beds(Bed.objects.filter(pk__in=beds, status=BedStatus.OCCUPIED), at)
    return count


def _free_beds(queryset, at) -> int:
    rows = list(queryset)
    for bed in rows:
        bed.status = _walk(BED_LIFECYCLE, bed.status, "discharge", "markReady")
        bed.clear_patient()
        bed.status_since = at
    Bed.objects.bulk_update(
        rows,
        [
            "status",
            "status_since",
            "patient_initials",
            "patient_age",
            "patient_sex",
            "admitted_at",
            "expected_discharge",
            "isolation",
        ],
        batch_size=500,
    )
    return len(rows)


def _fill_beds(beds, tick, at, *, ages=(18, 85), female=False, stay=(1, 6)) -> int:
    rand = tick.rand
    for bed in beds:
        bed.status = _walk(BED_LIFECYCLE, bed.status, "reserve", "admit")
        bed.status_since = bed.admitted_at = at
        bed.patient_initials = _letters(rand)
        bed.patient_age = rand.randint(*ages)
        bed.patient_sex = "F" if female else rand.choice("FM")
        days = max(1, round(rand.uniform(*stay) * tick.stay))
        bed.expected_discharge = timezone.localdate(at) + timedelta(days=days)
    Bed.objects.bulk_update(
        beds,
        [
            "status",
            "status_since",
            "admitted_at",
            "patient_initials",
            "patient_age",
            "patient_sex",
            "expected_discharge",
        ],
        batch_size=500,
    )
    return len(beds)


def _emergency(site, tick, start, end, held, summary) -> None:
    rand = tick.rand
    local = timezone.localtime(start)
    hours = (end - start).total_seconds() / 3600
    mean = site.arrivals_per_day * ARRIVAL_SHAPE[local.hour] / ARRIVAL_TOTAL * WEEKDAY[local.weekday()]
    mean = mean * tick.arrivals + tick.surge.get(site.hospital.pk, 0.0)
    arrived = poisson(rand, mean * hours)
    inputs = inputs_for(site, end, held)
    capacity = capacity_per_hour(inputs)
    wait = round(er_wait_minutes(mean, capacity) * rand.uniform(0.85, 1.15))
    waiting = round(mean * wait / 60 * 0.5 * rand.uniform(0.85, 1.15))
    left = poisson(rand, min(mean, capacity) * hours)
    tick.count(site.hospital, "er.arrivals", arrived)
    tick.count(site.hospital, "er.departures", left)
    summary["emergencyArrivals"] = summary.get("emergencyArrivals", 0) + arrived
    # Emergency beds: about as many in use as the hour's load keeps busy.
    beds = Bed.objects.filter(hospital=site.hospital, bed_type=BedType.EMERGENCY).exclude(pk__in=held)
    want = min(
        beds.exclude(status=BedStatus.OUT_OF_SERVICE).count(), round(mean * MEAN_TREATMENT_HOURS * 0.7)
    )
    occupied = list(beds.filter(status=BedStatus.OCCUPIED).order_by("?"))
    if len(occupied) > want:
        _free_beds(Bed.objects.filter(pk__in=[b.pk for b in occupied[: len(occupied) - want]]), end)
    elif len(occupied) < want:
        free = list(beds.filter(status=BedStatus.FREE).order_by("?")[: want - len(occupied)])
        _fill_beds(free, tick, end, ages=(1, 90), stay=(0, 1))
    department.update_department_status(
        hospital=site.hospital,
        status=er_status_for(waiting, wait, site.er_beds),
        wait_minutes=wait,
        waiting_count=waiting,
        actor=tick.actor,
        log_minor=False,
    )


def _wards(site, tick, start, end, held, summary) -> None:
    rand = tick.rand
    local = timezone.localtime(start)
    minutes = (end - start).total_seconds() / 60
    today = local.date()
    ward_ids = list(site.wards)
    if not ward_ids:
        return
    chance = _discharge_chance(local.hour, minutes)
    if chance:
        due = (
            Bed.objects.filter(ward_id__in=ward_ids, status=BedStatus.OCCUPIED, expected_discharge__lte=today)
            .exclude(pk__in=held)
            .exclude(bed_type=BedType.EMERGENCY)
        )
        leaving = [b.pk for b in due if rand.random() < chance]
        gone = _free_beds(Bed.objects.filter(pk__in=leaving), end)
        tick.count(site.hospital, "wards.discharges", gone)
        summary["discharges"] = summary.get("discharges", 0) + gone
    if ADMISSION_HOURS[0] <= local.hour < ADMISSION_HOURS[1]:
        for ward_id, rule in site.wards.items():
            beds = Bed.objects.filter(ward_id=ward_id).exclude(status=BedStatus.OUT_OF_SERVICE)
            total = beds.count()
            taken = beds.filter(status__in=(BedStatus.OCCUPIED, BedStatus.RESERVED)).count()
            gap = tick.occupancy * total - taken
            if gap < 1:
                continue
            n = min(round(gap), poisson(rand, gap * 0.012 * minutes))
            free = list(beds.filter(status=BedStatus.FREE).exclude(pk__in=held).order_by("label")[:n])
            if free:
                kind = free[0].bed_type
                made = _fill_beds(
                    free,
                    tick,
                    end,
                    ages=(rule.lo, rule.hi),
                    female=rule.female_only,
                    stay=STAY_DAYS.get(kind, STAY_DAYS[BedType.GENERAL]),
                )
                tick.count(site.hospital, "wards.admissions", made)
                summary["admissions"] = summary.get("admissions", 0) + made


def _blood(site, tick, start, end, held, summary) -> None:
    if not site.blood_per_day and not site.donations_per_day:
        return
    rand = tick.rand
    local = timezone.localtime(start)
    hours = (end - start).total_seconds() / 3600
    skip = blood._demo_groups(site.hospital)
    use = site.blood_per_day * tick.blood_use * BLOOD_SHAPE[local.hour] / sum(BLOOD_SHAPE) * 24 * hours / 24
    use += tick.blood_surge.get(site.hospital.pk, 0.0) * hours
    issued = []
    wanted = {}
    for _ in range(poisson(rand, use)):
        key = (pick(rand, blood.GROUP_SHARE), pick(rand, blood.ISSUE_MIX))
        if key not in skip:
            wanted[key] = wanted.get(key, 0) + 1
    for (group, component), n in wanted.items():
        units = list(
            blood._usable(site.hospital, group, component, end)
            .exclude(pk__in=held)
            .order_by("expires_at", "pk")[:n]
        )
        for unit in units:
            unit.status, unit.status_since = _walk(BloodUnit.machine, unit.status, "issue"), end
        issued += units
    BloodUnit.objects.bulk_update(issued, ["status", "status_since"], batch_size=500)
    tick.count(site.hospital, "blood.issued", len(issued))
    summary["unitsIssued"] = summary.get("unitsIssued", 0) + len(issued)

    open_hours = blood.CLINIC_HOURS
    if open_hours[0] <= local.hour < open_hours[1] and site.donations_per_day:
        rate = site.donations_per_day * tick.donations / (open_hours[1] - open_hours[0]) * hours
        units, tests = [], []
        donations = poisson(rand, rate)
        for _ in range(donations):
            group = pick(rand, blood.GROUP_SHARE)
            collected = start + timedelta(minutes=rand.uniform(0, 60 * hours))
            for component in blood.components(rand):
                if (group, component) in skip:
                    continue
                fails = rand.random() < blood.FAIL_SHARE
                location = blood._fridge(site.hospital, component)
                unit = BloodUnit(
                    hospital=site.hospital,
                    storage_location=location,
                    location=location.name if location else "Blood bank",
                    donation_number=blood._next_number(tick),
                    group=group,
                    component=component,
                    collected_at=collected,
                    expires_at=collected + timedelta(days=blood.SHELF_DAYS[component]),
                    status=_walk(
                        BloodUnit.machine, UnitStatus.QUARANTINED, "discard" if fails else "release"
                    ),
                    status_since=end,
                )
                units.append(unit)
        BloodUnit.objects.bulk_create(units, batch_size=500)
        for unit in units:
            failing = rand.choice(REQUIRED_TESTS) if unit.status == UnitStatus.DISCARDED else None
            for test in REQUIRED_TESTS:
                tests.append(
                    TestResult(
                        unit=unit,
                        test=test,
                        passed=test != failing,
                        reason="" if test != failing else "Reactive on screening",
                        recorded_by=tick.actor,
                    )
                )
                if test == failing:
                    break
        TestResult.objects.bulk_create(tests, batch_size=1000)
        tick.count(site.hospital, "blood.donated", donations)
        summary["donations"] = summary.get("donations", 0) + donations


def _expire(end) -> int:
    expirable = [s for (s, action) in BloodUnit.machine.transitions if action == "expire"]
    rows = list(BloodUnit.objects.filter(status__in=expirable, expires_at__lte=end))
    for unit in rows:
        unit.status, unit.status_since = _walk(BloodUnit.machine, unit.status, "expire"), end
    BloodUnit.objects.bulk_update(rows, ["status", "status_since"], batch_size=500)
    return len(rows)


def _theatres(site, tick, end, held) -> None:
    """Each room ends the hour in use if a booked case is running, otherwise available (cleaned)."""
    if not site.rooms:
        return
    changed = []
    for room in OperatingRoom.objects.filter(
        hospital=site.hospital, status__in=(OrStatus.AVAILABLE, OrStatus.IN_USE, OrStatus.CLEANING)
    ).exclude(pk__in=held):
        running = OrBooking.objects.filter(
            room=room, status=OrBookingStatus.BOOKED, starts_at__lte=end, ends_at__gt=end
        ).first()
        if running is not None and room.status != OrStatus.IN_USE:
            path = ("finishCleaning", "startCase") if room.status == OrStatus.CLEANING else ("startCase",)
            room.status, room.status_since = _walk(OR_LIFECYCLE, room.status, *path), running.starts_at
            changed.append(room)
        elif running is None and room.status != OrStatus.AVAILABLE:
            path = ("finishCase", "finishCleaning") if room.status == OrStatus.IN_USE else ("finishCleaning",)
            room.status, room.status_since = _walk(OR_LIFECYCLE, room.status, *path), end
            changed.append(room)
    OperatingRoom.objects.bulk_update(changed, ["status", "status_since"])


def _cleaning(end, held) -> None:
    rows = list(Bed.objects.filter(status=BedStatus.CLEANING).exclude(pk__in=held))
    for bed in rows:
        bed.status, bed.status_since = _walk(BED_LIFECYCLE, bed.status, "markReady"), end
    Bed.objects.bulk_update(rows, ["status", "status_since"], batch_size=500)


@transaction.atomic
def coarse_hour(tick, sites, start, end, summary: dict) -> None:
    """The city from `start` to `end` (at most an hour), summarised. One transaction: it is all or nothing."""
    tick.end = end
    held_beds, held_rooms, held_units = held_ids(Bed), held_ids(OperatingRoom), held_ids(BloodUnit)
    if not summary.get("hours"):
        summary["patientsSentHome"] = close_open_visits(start)
    summary["hours"] = summary.get("hours", 0) + 1
    staff.step(tick, start, end, [s.hospital for s in sites], audit=False)
    _cleaning(end, held_beds)
    for site in sites:
        if site.er_beds:
            _emergency(site, tick, start, end, held_beds, summary)
        _wards(site, tick, start, end, held_beds, summary)
        _blood(site, tick, start, end, held_units, summary)
        _theatres(site, tick, end, held_rooms)
    summary["unitsExpired"] = summary.get("unitsExpired", 0) + _expire(end)
    summary["shiftsMissed"] = summary.get("shiftsMissed", 0) + sum(tick.absent_now.values())
    tick.absent_now.clear()  # counted in the summary, not listed one by one
    cases.resolve_untouched(tick, end)
