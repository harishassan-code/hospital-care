"""Two weeks of hourly history per hospital for the trend charts (B20, read by B22), ending at the state the
rest of the seed just created, so a chart's last point matches the live figures.

Each series is a daily rhythm scaled to the hospital, plus noise from the hospital's own random stream:
emergency arrivals peak late morning and evening and are lowest before dawn, more on Mondays; beds are fullest
in the morning, before the day's discharges; theatres are busy on weekday daytimes. Counts per hour are random
draws around the rhythm (Poisson); levels drift and are walked back from the current value. The rhythm shapes
and rates are in docs/product/demo-data.md.
"""

import bisect
import random
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.ambulances.models import Ambulance, AmbulanceStatus
from apps.blood.models import BloodUnit, Component, UnitStatus
from apps.emergencies.models import ErStatus
from apps.equipment.models import Equipment, EquipmentStatus, EquipmentType
from apps.hospitals.models import Bed, BedStatus, BedType, Hospital
from apps.metrics import catalog
from apps.metrics.models import MetricSnapshot
from apps.operating_rooms.models import OperatingRoom, OrStatus
from apps.staffing.models import Shift, StaffRole

from .resources import poisson

HOURS = 14 * 24

# Share of a day's emergency arrivals in each hour (Karachi time), before scaling: lowest 03:00-05:00, highest
# 10:00-13:00 and 18:00-21:00.
ARRIVAL_SHAPE = [
    0.45,
    0.38,
    0.33,
    0.3,
    0.3,
    0.35,
    0.5,
    0.75,
    1.0,
    1.25,
    1.4,
    1.45,
    1.4,
    1.3,
    1.25,
    1.2,
    1.2,
    1.25,
    1.35,
    1.4,
    1.3,
    1.1,
    0.85,
    0.6,
]
ARRIVAL_TOTAL = sum(ARRIVAL_SHAPE)
WEEKDAY = [1.12, 1.05, 1.0, 1.0, 0.96, 0.95, 0.93]  # Monday first
# Beds are fullest around 08:00 and emptiest around 17:00, after the day's discharges and before evening
# admissions.
OCCUPANCY_SHAPE = [
    0.6,
    0.7,
    0.8,
    0.9,
    0.95,
    1.0,
    1.0,
    1.0,
    1.0,
    0.8,
    0.5,
    0.2,
    -0.1,
    -0.4,
    -0.7,
    -0.9,
    -1.0,
    -1.0,
    -0.8,
    -0.5,
    -0.2,
    0.1,
    0.3,
    0.5,
]
THEATRE_SHAPE = [0.05] * 8 + [0.8, 0.85, 0.9, 0.85, 0.7, 0.85, 0.85, 0.75, 0.5] + [0.15, 0.1] + [0.05] * 5
BLOOD_SHAPE = [0.4] * 7 + [
    0.9,
    1.2,
    1.4,
    1.4,
    1.3,
    1.3,
    1.3,
    1.2,
    1.2,
    1.1,
    1.0,
    0.9,
    0.8,
    0.7,
    0.6,
    0.5,
    0.4,
]


def _hours(now):
    end = timezone.localtime(now).replace(minute=0, second=0, microsecond=0)
    return [end - timedelta(hours=HOURS - 1 - k) for k in range(HOURS)]


def _walk(rand: random.Random, n: int, step: float) -> list[float]:
    """A random walk that ends at 0, read backwards from the last hour."""
    out, value = [0.0] * n, 0.0
    for k in range(n - 2, -1, -1):
        value += rand.gauss(0, step)
        out[k] = value
    return out


def er_wait_minutes(arrivals_per_hour: float, capacity_per_hour: float) -> float:
    """The average wait for how busy a department is (load = arrivals over what it can see in an hour): about
    a quarter of an hour when quiet, rising steeply as the load passes 1, at most four hours. Shared with the
    simulation (B21)."""
    load = arrivals_per_hour / capacity_per_hour if capacity_per_hour else 1.0
    return min(240.0, 15 + 30 * load**3)


def _er_series(rand, hours, per_day: int, er_beds: int, final: tuple[int, int] | None):
    """Arrivals and departures per hour, and the waiting count and wait at the end of each hour. A department
    is sized to see a quarter more than its average arrivals; people waiting follow from arrivals times the
    wait (Little's law), smoothed hour to hour."""
    arrivals, departures, waiting, wait = [], [], [], []
    capacity = per_day / 24 * 1.25
    queue = 0.0
    for at in hours:
        mean = (
            per_day * ARRIVAL_SHAPE[at.hour] / ARRIVAL_TOTAL * WEEKDAY[at.weekday()] * rand.uniform(0.9, 1.1)
        )
        arrived = poisson(rand, mean)
        minutes = er_wait_minutes(mean, capacity) * rand.uniform(0.85, 1.15)
        queue = 0.5 * queue + 0.5 * mean * minutes / 60
        arrivals.append(arrived)
        departures.append(poisson(rand, min(mean, capacity)))
        waiting.append(round(queue * rand.uniform(0.85, 1.15)))
        wait.append(round(minutes))
    if final is not None:  # bring the last hours to the figures the department reports now
        for k in range(1, 4):
            blend = k / 3
            waiting[-4 + k] = round(waiting[-4 + k] * (1 - blend) + final[0] * blend)
            wait[-4 + k] = round(wait[-4 + k] * (1 - blend) + final[1] * blend)
    return arrivals, departures, waiting, wait


def er_status_for(waiting: int, wait: int, er_beds: int) -> str:
    if wait >= 150 or waiting >= er_beds * 1.5:
        return ErStatus.DIVERTING
    if wait >= 60 or waiting >= er_beds:
        return ErStatus.BUSY
    return ErStatus.ACCEPTING


def seed_history(hospital: Hospital, rand: random.Random, now, *, er_per_day: int, final_er=None):
    """Writes the hospital's two weeks of snapshots, unless it has some. Returns the emergency department's
    last (waiting, wait minutes), or None when it has no emergency beds."""
    if MetricSnapshot.objects.filter(hospital=hospital).exists():
        return None
    hours = _hours(now)
    rows: list[MetricSnapshot] = []

    def add(metric: str, values):
        rows.extend(
            MetricSnapshot(hospital=hospital, metric=metric, at=at, value=v)
            for at, v in zip(hours, values, strict=True)
        )

    beds = (
        Bed.objects.filter(hospital=hospital)
        .values("bed_type")
        .annotate(
            in_service=Count("id", filter=~Q(status=BedStatus.OUT_OF_SERVICE)),
            occupied=Count("id", filter=Q(status=BedStatus.OCCUPIED)),
        )
    )
    by_type = {row["bed_type"]: row for row in beds}
    icu_occupied = []
    for bed_type in BedType.values:
        row = by_type.get(bed_type)
        if not row or not row["in_service"]:
            continue
        total, now_occupied = row["in_service"], row["occupied"]
        swing, walk = total * 0.04, _walk(rand, HOURS, max(0.3, total * 0.01))
        now_shape = OCCUPANCY_SHAPE[hours[-1].hour]
        series = [
            max(0, min(total, round(now_occupied + swing * (OCCUPANCY_SHAPE[at.hour] - now_shape) + walk[k])))
            for k, at in enumerate(hours)
        ]
        series[-1] = now_occupied
        add(catalog.beds_occupied(bed_type), series)
        add(catalog.beds_in_service(bed_type), [total] * HOURS)
        if bed_type in (BedType.ICU, BedType.NICU):
            icu_occupied = [a + b for a, b in zip(icu_occupied or [0] * HOURS, series, strict=True)]

    er_beds = by_type.get(BedType.EMERGENCY, {}).get("in_service", 0)
    last_er = None
    if er_beds and er_per_day:
        arrivals, departures, waiting, wait = _er_series(rand, hours, er_per_day, er_beds, final_er)
        add(catalog.ER_ARRIVALS, arrivals)
        add(catalog.ER_DEPARTURES, departures)
        add(catalog.ER_WAITING, waiting)
        add(catalog.ER_WAIT_MINUTES, wait)
        last_er = (waiting[-1], wait[-1])

    usable = BloodUnit.objects.filter(
        hospital=hospital, component=Component.RED_CELLS, status=UnitStatus.AVAILABLE, expires_at__gt=now
    ).count()
    if BloodUnit.objects.filter(hospital=hospital).exists():
        daily = max(2.0, usable / 5)  # a blood bank keeps about five days of red cells
        issued = [poisson(rand, daily / 24 * BLOOD_SHAPE[at.hour] * rand.uniform(0.8, 1.2)) for at in hours]
        donated = [poisson(rand, daily / 10 * 1.0) if 9 <= at.hour < 19 else 0 for at in hours]
        level, stock = usable, [0] * HOURS
        for k in range(HOURS - 1, -1, -1):
            stock[k] = level
            level = max(0, level + issued[k] - donated[k])
        add(catalog.BLOOD_RED_CELLS, stock)
        add(catalog.BLOOD_ISSUED, issued)
        add(catalog.BLOOD_DONATED, donated)

    rooms = OperatingRoom.objects.filter(hospital=hospital).exclude(status=OrStatus.OUT_OF_SERVICE).count()
    if rooms:
        in_use_now = OperatingRoom.objects.filter(hospital=hospital, status=OrStatus.IN_USE).count()
        series = [
            min(rooms, poisson(rand, rooms * THEATRE_SHAPE[at.hour] * (0.35 if at.weekday() == 6 else 1.0)))
            for at in hours
        ]
        series[-1] = in_use_now
        add(catalog.OR_IN_USE, series)
        add(catalog.OR_ROOMS, [rooms] * HOURS)

    ventilators = Equipment.objects.filter(hospital=hospital, equipment_type=EquipmentType.VENTILATOR)
    if ventilators.exists():
        count = ventilators.exclude(status=EquipmentStatus.OUT_OF_SERVICE).count()
        in_use_now = ventilators.filter(status=EquipmentStatus.IN_USE).count()
        base = icu_occupied or [in_use_now] * HOURS
        ratio = in_use_now / base[-1] if base[-1] else 0.6
        series = [min(count, max(0, round(b * ratio + rand.gauss(0, 0.6)))) for b in base]
        series[-1] = in_use_now
        add(catalog.VENTILATORS_IN_USE, series)

    for role in StaffRole.values:
        shifts = Shift.objects.filter(hospital=hospital, staff__role=role, clocked_in_at__isnull=False)
        ins = sorted(shifts.values_list("clocked_in_at", flat=True))
        outs = sorted(t for t in shifts.values_list("clocked_out_at", flat=True) if t is not None)
        if not ins:
            continue
        add(
            catalog.staff_on_duty(role),
            [
                bisect.bisect_right(ins, at + timedelta(minutes=59))
                - bisect.bisect_right(outs, at + timedelta(minutes=59))
                for at in hours
            ],
        )

    fleet = Ambulance.objects.filter(hospital=hospital).exclude(status=AmbulanceStatus.OUT_OF_SERVICE).count()
    if fleet:
        add(catalog.AMBULANCE_TRIPS, [poisson(rand, fleet * 0.12 * ARRIVAL_SHAPE[at.hour]) for at in hours])

    MetricSnapshot.objects.bulk_create(rows, batch_size=2000)
    return last_er
