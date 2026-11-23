"""Staff rosters (B20): every hospital's doctors and nurses, sized to its wards, with shifts from two weeks
ago to a week ahead; clock times only for shifts that started; on duty means clocked in and not out."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.core.seed.staffing import AHEAD_DAYS, PAST_DAYS
from apps.hospitals.models import Bed, BedType, Hospital
from apps.specialists.models import Specialist
from apps.staffing.models import Shift, StaffMember, StaffRole

pytestmark = pytest.mark.django_db


def test_every_hospital_has_a_roster_sized_to_its_beds():
    call_command("seed_demo", stdout=None)
    now = timezone.now()
    for hospital in Hospital.objects.all():
        nurses = StaffMember.objects.filter(hospital=hospital, role=StaffRole.NURSE).count()
        doctors = StaffMember.objects.filter(hospital=hospital, role=StaffRole.DOCTOR).count()
        beds = Bed.objects.filter(hospital=hospital).count()
        icu = Bed.objects.filter(hospital=hospital, bed_type__in=(BedType.ICU, BedType.NICU)).count()
        assert doctors >= 2, hospital.name
        if beds:
            # Three shifts a day: at least one nurse per eight ward patients, and per two in intensive care.
            assert nurses >= 3 * ((beds - icu) / 8 + icu / 2) * 0.9, hospital.name
            on_duty = Shift.objects.filter(hospital=hospital).on_duty_at(now)
            assert on_duty.filter(staff__role=StaffRole.NURSE).exists(), hospital.name
            assert on_duty.filter(staff__role=StaffRole.DOCTOR).exists(), hospital.name


def test_shifts_span_two_weeks_back_to_one_ahead_with_clock_times_only_when_started():
    call_command("seed_demo", stdout=None)
    now = timezone.now()
    shifts = Shift.objects.all()
    first = timezone.localdate(shifts.order_by("starts_at").first().starts_at)
    last = timezone.localdate(shifts.order_by("-starts_at").first().starts_at)
    today = timezone.localdate(now)
    assert first == today - timedelta(days=PAST_DAYS) and last == today + timedelta(days=AHEAD_DAYS)
    assert not shifts.filter(starts_at__gt=now, clocked_in_at__isnull=False).exists()
    assert not shifts.filter(ends_at__gt=now, clocked_out_at__isnull=False).exists()
    past = shifts.filter(ends_at__lte=now)
    missed = past.filter(clocked_in_at__isnull=True).count() / past.count()
    assert 0 < missed < 0.06  # a few missed shifts, as on any rota
    late = past.filter(clocked_in_at__gt=models_f("starts_at", minutes=10)).count() / past.count()
    assert 0.02 < late < 0.12
    assert not past.filter(clocked_in_at__isnull=False, clocked_out_at__isnull=True).exists()


def models_f(field, *, minutes):
    from django.db.models import F

    return F(field) + timedelta(minutes=minutes)


def test_on_duty_means_clocked_in_and_not_out(make_hospital):
    hospital = make_hospital()
    nurse = StaffMember.objects.create(hospital=hospital, name="Hina Test", role="nurse", department="ICU")
    now = timezone.now()
    hour = timedelta(hours=1)

    def shift(**times):
        return Shift.objects.create(
            staff=nurse, hospital=hospital, starts_at=now - hour, ends_at=now + hour, **times
        )

    working = shift(clocked_in_at=now - hour)
    gone = shift(clocked_in_at=now - hour, clocked_out_at=now - timedelta(minutes=5))
    missed = shift()
    assert list(Shift.objects.on_duty_at(now)) == [working]
    assert set(Shift.objects.covering(now)) == {working, gone, missed}


def test_the_new_hospitals_consultants_come_from_their_rosters_and_a_rerun_tops_up_their_windows():
    call_command("seed_demo", stdout=None)
    eastgate = Hospital.objects.get(name="Eastgate Trauma Centre")
    consultants = Specialist.objects.filter(hospital=eastgate)
    assert consultants.count() >= 4
    assert set(consultants.values_list("specialty", flat=True)) <= set(
        StaffMember.objects.filter(hospital=eastgate).values_list("department", flat=True)
    )
    on_call_now = Specialist.objects.filter(hospital=eastgate).available_at(timezone.now())
    assert on_call_now.exists()  # someone is always on call: day and night consultants
    first = consultants.first()
    first.on_call_windows.order_by("-starts_at").first().delete()
    call_command("seed_demo", stdout=None)
    assert first.on_call_windows.count() == 7
    assert Specialist.objects.filter(hospital=eastgate).count() == consultants.count()
