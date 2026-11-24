"""Two weeks of hourly history (B20): every figure for every named hospital, ending at the live state, with
the daily rhythms the charts should show; and each emergency department's status read from its last hour."""

import statistics

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.blood.models import BloodUnit, Component, UnitStatus
from apps.core.seed.history import HOURS, er_status_for
from apps.core.seed.profiles import PROFILES
from apps.emergencies.models import EmergencyStatus
from apps.hospitals.models import Bed, BedStatus, BedType, Hospital
from apps.metrics import catalog
from apps.metrics.models import MetricSnapshot

pytestmark = pytest.mark.django_db

# Real Karachi hospitals the demo network must never be mistaken for (spec B20, Q4).
REAL = [
    "Aga Khan",
    "Jinnah",
    "Civil Hospital",
    "Liaquat",
    "Indus",
    "South City",
    "Ziauddin",
    "Abbasi Shaheed",
    "Lyari General",
    "Qatar",
    "Patel",
    "Tabba",
    "NICVD",
    "SIUT",
    "Kharadar",
    "Saifee",
    "Dow",
    "Hill Park",
]


def series(hospital, metric):
    return list(
        MetricSnapshot.objects.filter(hospital=hospital, metric=metric)
        .order_by("at")
        .values_list("at", "value")
    )


def test_every_named_hospital_has_two_weeks_of_hourly_figures_ending_now():
    call_command("seed_demo", stdout=None)
    now = timezone.localtime()
    for hospital in Hospital.objects.exclude(type="bloodBank"):
        icu = series(hospital, catalog.beds_occupied(BedType.ICU)) or series(
            hospital, catalog.beds_occupied(BedType.NICU)
        )
        general = series(hospital, catalog.beds_occupied(BedType.GENERAL))
        assert len(general) == HOURS, hospital.name
        last_at = timezone.localtime(general[-1][0])
        assert last_at.hour == now.hour and (now - last_at).total_seconds() < 3600
        live = Bed.objects.filter(
            hospital=hospital, bed_type=BedType.GENERAL, status=BedStatus.OCCUPIED
        ).count()
        assert general[-1][1] == live, hospital.name  # the chart's last point is the live figure
        assert all(0 <= v <= 400 for _, v in general + icu)
        assert len(series(hospital, catalog.staff_on_duty("nurse"))) == HOURS


def test_emergency_arrivals_follow_the_day_and_the_profile():
    call_command("seed_demo", stdout=None)
    for name, profile in PROFILES.items():
        if not profile.er_arrivals_per_day:
            continue
        rows = series(Hospital.objects.get(name=name), catalog.ER_ARRIVALS)
        per_day = sum(v for _, v in rows) / 14
        assert 0.8 * profile.er_arrivals_per_day < per_day < 1.2 * profile.er_arrivals_per_day, name
        night = statistics.mean(v for at, v in rows if 2 <= timezone.localtime(at).hour <= 5)
        day = statistics.mean(v for at, v in rows if 10 <= timezone.localtime(at).hour <= 13)
        assert day > 2.5 * night, name  # quietest before dawn, busiest late morning


def test_blood_history_ends_at_the_usable_stock_and_is_never_negative():
    call_command("seed_demo", stdout=None)
    now = timezone.now()
    for hospital in Hospital.objects.filter(pk__in=BloodUnit.objects.values("hospital")):
        rows = series(hospital, catalog.BLOOD_RED_CELLS)
        usable = BloodUnit.objects.filter(
            hospital=hospital, component=Component.RED_CELLS, status=UnitStatus.AVAILABLE, expires_at__gt=now
        ).count()
        assert rows[-1][1] == usable and min(v for _, v in rows) >= 0, hospital.name
        assert sum(v for _, v in series(hospital, catalog.BLOOD_ISSUED)) > 0


def test_each_department_reports_what_its_last_hour_shows_and_the_main_one_is_the_demo_scripts():
    call_command("seed_demo", stdout=None)
    main = EmergencyStatus.objects.get(hospital__name="CityCare General Hospital")
    assert (main.status, main.waiting_count, main.wait_minutes) == ("accepting", 7, 24)
    for status in EmergencyStatus.objects.select_related("hospital"):
        waiting = series(status.hospital, catalog.ER_WAITING)[-1][1]
        wait = series(status.hospital, catalog.ER_WAIT_MINUTES)[-1][1]
        assert (status.waiting_count, status.wait_minutes) == (waiting, wait), status.hospital.name
        assert 5 <= status.wait_minutes <= 240
    assert not EmergencyStatus.objects.filter(hospital__type="bloodBank").exists()
    assert EmergencyStatus.objects.count() == Hospital.objects.exclude(type="bloodBank").count()


def test_a_rerun_adds_no_history():
    call_command("seed_demo", stdout=None)
    count = MetricSnapshot.objects.count()
    call_command("seed_demo", stdout=None)
    assert MetricSnapshot.objects.count() == count


def test_status_thresholds():
    assert er_status_for(3, 20, er_beds=10) == "accepting"
    assert er_status_for(3, 75, er_beds=10) == "busy"
    assert er_status_for(12, 30, er_beds=10) == "busy"
    assert er_status_for(16, 30, er_beds=10) == "diverting"
    assert er_status_for(2, 160, er_beds=10) == "diverting"


def test_no_hospital_is_named_like_a_real_one():
    call_command("seed_demo", stdout=None)
    for name in Hospital.objects.values_list("name", flat=True):
        assert not any(real.lower() in name.lower() for real in REAL), name
