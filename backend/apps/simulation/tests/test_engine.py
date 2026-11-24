"""The simulation engine's rules (B21): what it does in a step, and what it never touches."""

import random
from datetime import UTC, datetime, timedelta

import pytest
from django.contrib.contenttypes.models import ContentType

from apps.audit.models import AuditLog
from apps.blood.models import BloodUnit, UnitStatus
from apps.core import clock
from apps.emergencies.models import EmergencyRequest, ErVisit, RequestItem, VisitStatus
from apps.emergencies.wait import Inputs, estimate
from apps.hospitals.models import Bed, BedStatus, BedType, Department, Ward
from apps.matching.models import Reservation
from apps.notifications.models import Notification
from apps.operating_rooms.models import OperatingRoom, OrBooking, OrStatus
from apps.simulation import blood, cases, ed, engine, events, staff, theatres, wards
from apps.simulation.actor import system_user
from apps.simulation.models import SimEvent
from apps.simulation.world import build_sites
from apps.staffing.models import Shift, StaffMember

pytestmark = pytest.mark.django_db

NOON = datetime(2026, 11, 24, 7, 0, tzinfo=UTC)  # 12:00 in Karachi


@pytest.fixture(autouse=True)
def on(settings):
    settings.SIMULATION_ENABLED = True


@pytest.fixture
def city(make_hospital, make_user):
    """One small hospital: an emergency department of three beds, a medical ward of three, a doctor and two
    nurses on today's day shift, a theatre and some blood."""
    hospital = make_hospital()
    em = Department.objects.create(hospital=hospital, name="Emergency medicine")
    ed_ward = Ward.objects.create(
        code="ed", hospital=hospital, department=em, name="Emergency", kind="Emergency"
    )
    med = Ward.objects.create(code="medA", hospital=hospital, name="Medical A", kind="General medicine")
    for n in range(1, 4):
        Bed.objects.create(label=f"ED-{n:02d}", ward=ed_ward, bed_type=BedType.EMERGENCY)
        Bed.objects.create(label=f"MA-{n:02d}", ward=med)
    for name, role in [("Dr. Test One", "doctor"), ("Nurse A", "nurse"), ("Nurse B", "nurse")]:
        member = StaffMember.objects.create(hospital=hospital, name=name, role=role, department=em.name)
        Shift.objects.create(
            staff=member,
            hospital=hospital,
            starts_at=NOON - timedelta(hours=4),
            ends_at=NOON + timedelta(hours=8),
            clocked_in_at=NOON - timedelta(hours=4),
        )
    make_user("nurse", email="nurse@example.com", hospital=hospital)
    make_user("bloodBank", email="bank@example.com", hospital=hospital)
    return hospital


def make_tick(**overrides):
    state = engine.state()
    tick = engine.make_tick(state, build_sites())
    tick.rand = random.Random(3)
    for name, value in overrides.items():
        setattr(tick, name, value)
    return tick


def site_of(hospital):
    return next(s for s in build_sites() if s.hospital == hospital)


def test_patients_arrive_and_are_seen_in_triage_order(city):
    tick = make_tick()
    site = site_of(city)
    with clock.at(NOON):
        minor = ed.arrive(
            hospital=city,
            triage=5,
            age_band="18-39",
            sex="F",
            complaint="minor",
            actor=tick.actor,
            rand=tick.rand,
        )
        urgent = ed.arrive(
            hospital=city,
            triage=2,
            age_band="40-64",
            sex="M",
            complaint="cardiac",
            actor=tick.actor,
            rand=tick.rand,
        )
        tick.arrivals = 0  # no new arrivals in this step
        ed.step(site, tick, NOON - timedelta(minutes=5), NOON, set())
    urgent.refresh_from_db()
    minor.refresh_from_db()
    assert urgent.status == VisitStatus.TREATING and urgent.bed.status == BedStatus.OCCUPIED
    assert urgent.bed.patient_age is not None and urgent.bed.patient_initials  # never a name
    assert AuditLog.objects.filter(action="ervisit.treatment_started", actor_email=tick.actor.email).exists()


def test_a_bed_held_for_a_case_is_never_used(city, make_user):
    tick = make_tick(arrivals=0)
    held = Bed.objects.filter(bed_type=BedType.EMERGENCY).order_by("label")
    with clock.at(NOON):
        visits = [
            ed.arrive(
                hospital=city,
                triage=2,
                age_band="40-64",
                sex="M",
                complaint="trauma",
                actor=tick.actor,
                rand=tick.rand,
            )
            for _ in range(3)
        ]
        ed.step(site_of(city), tick, NOON - timedelta(minutes=5), NOON, {held[0].pk})
    held_bed = held[0]
    held_bed.refresh_from_db()
    assert held_bed.status == BedStatus.FREE
    assert sorted(v.bed.label for v in ErVisit.objects.filter(status=VisitStatus.TREATING)) == [
        "ED-02",
        "ED-03",
    ]
    assert ErVisit.objects.filter(status=VisitStatus.WAITING).count() == len(visits) - 2


def test_an_admission_goes_to_a_ward_bed_or_waits_in_the_department(city):
    tick = make_tick(arrivals=0, admit={2: 1.0}, transfer=0)
    with clock.at(NOON):
        visit = ed.arrive(
            hospital=city,
            triage=2,
            age_band="40-64",
            sex="M",
            complaint="cardiac",
            actor=tick.actor,
            rand=tick.rand,
        )
        ed.start_treatment(
            visit, bed=Bed.objects.get(label="ED-01"), minutes=1, actor=tick.actor, rand=tick.rand
        )
        Bed.objects.filter(label__startswith="MA-").update(status=BedStatus.OCCUPIED)
    with clock.at(NOON + timedelta(minutes=5)):
        ed.step(site_of(city), tick, NOON, NOON + timedelta(minutes=5), set())
    visit.refresh_from_db()
    assert visit.status == VisitStatus.BOARDING and visit.bed.label == "ED-01"  # no ward bed: waits
    Bed.objects.filter(label="MA-02").update(status=BedStatus.FREE)
    with clock.at(NOON + timedelta(minutes=10)):
        ed.step(site_of(city), tick, NOON + timedelta(minutes=5), NOON + timedelta(minutes=10), set())
    visit.refresh_from_db()
    assert visit.status == VisitStatus.LEFT and visit.outcome == "admitted"
    assert visit.ward_bed.label == "MA-02" and visit.ward_bed.status == BedStatus.OCCUPIED
    assert visit.ward_bed.expected_discharge is not None
    assert Bed.objects.get(label="ED-01").status == BedStatus.CLEANING


def test_beds_are_cleaned_and_free_again_except_held_ones(city):
    tick = make_tick()
    Bed.objects.filter(label__in=["ED-01", "ED-02"]).update(status=BedStatus.CLEANING, status_since=NOON)
    held = Bed.objects.get(label="ED-02")
    with clock.at(NOON + timedelta(minutes=31)):
        wards.cleaning_step(tick, NOON + timedelta(minutes=31), {held.pk}, [city])
    assert Bed.objects.get(label="ED-01").status == BedStatus.FREE  # 10-30 minutes for an emergency bed
    assert Bed.objects.get(label="ED-02").status == BedStatus.CLEANING


def test_only_patients_with_a_planned_discharge_go_home(city):
    tick = make_tick(occupancy=0)
    today = clock.localdate()
    Bed.objects.filter(label="MA-01").update(
        status=BedStatus.OCCUPIED, expected_discharge=today - timedelta(days=1)
    )
    Bed.objects.filter(label="MA-02").update(status=BedStatus.OCCUPIED, expected_discharge=None)  # a nurse's
    late_morning = datetime(2026, 11, 24, 6, 0, tzinfo=UTC)  # 11:00
    for k in range(12):
        start = late_morning + timedelta(minutes=5 * k)
        with clock.at(start + timedelta(minutes=5)):
            wards.step(site_of(city), tick, start, start + timedelta(minutes=5), set())
    assert Bed.objects.get(label="MA-01").status != BedStatus.OCCUPIED
    assert Bed.objects.get(label="MA-02").status == BedStatus.OCCUPIED


def _unit(hospital, number, group="O+", **extra):
    return BloodUnit.objects.create(
        hospital=hospital,
        donation_number=number,
        group=group,
        component="redCells",
        collected_at=NOON - timedelta(days=10),
        expires_at=NOON + timedelta(days=extra.pop("days", 20)),
        status=UnitStatus.AVAILABLE,
        location="Blood fridge",
        **extra,
    )


def test_blood_is_issued_oldest_first_but_never_demo_stock_or_held_units(city):
    tick = make_tick()
    site = site_of(city)
    old = _unit(city, "G7731 26 000001", days=5)
    held = _unit(city, "G7731 26 000002", days=3)
    newer = _unit(city, "G7731 26 000003", days=30)
    demo = _unit(city, "G7731 26 000004", group="O-", days=1, demo_stock=True)
    with clock.at(NOON):
        assert blood.issue(site, tick, NOON, "O+", "redCells", {held.pk})
        assert not blood.issue(site, tick, NOON, "O-", "redCells", set())
    assert BloodUnit.objects.get(pk=old.pk).status == UnitStatus.ISSUED
    assert BloodUnit.objects.get(pk=held.pk).status == UnitStatus.AVAILABLE
    assert BloodUnit.objects.get(pk=newer.pk).status == UnitStatus.AVAILABLE
    assert BloodUnit.objects.get(pk=demo.pk).status == UnitStatus.AVAILABLE


def test_donations_are_screened_hours_later_and_a_group_at_zero_alerts_once(city):
    tick = make_tick()
    site = site_of(city)
    with clock.at(NOON):
        blood.donate(site, tick, NOON, "A+", skip=set())
    unit = BloodUnit.objects.filter(donation_number__startswith="G7799").first()
    assert unit.status == UnitStatus.QUARANTINED
    with clock.at(NOON + timedelta(hours=7)):
        blood.screen(site, tick, NOON + timedelta(hours=7))
    unit.refresh_from_db()
    assert unit.status in (UnitStatus.AVAILABLE, UnitStatus.DISCARDED)
    assert unit.tests.exists()
    _unit(city, "G7731 26 000010", group="B-")
    _unit(city, "G7731 26 000011", group="B-")
    with clock.at(NOON):
        blood.issue(site, tick, NOON, "B-", "redCells", set())
        blood.issue(site, tick, NOON, "B-", "redCells", set())  # the last one: B- at zero
    assert Notification.objects.filter(kind="simulation.blood_zero_B-").count() == 1
    _unit(city, "G7731 26 000012", group="B-")
    with clock.at(NOON + timedelta(minutes=10)):
        blood.issue(site, tick, NOON + timedelta(minutes=10), "B-", "redCells", set())
    assert Notification.objects.filter(kind="simulation.blood_zero_B-").count() == 1  # not again so soon


def test_alerts_wait_half_an_hour_of_city_time(city):
    tick = make_tick()
    args = {"kind": "x", "hospital": city, "module": "beds", "message": "m", "link": "", "actor": tick.actor}
    assert events.alert(tick.state, at=NOON, **args)
    tick.state.alerts_sent[f"{city.pk}:x"][1] = "2000-01-01T00:00:00+00:00"  # long ago in real time
    assert not events.alert(tick.state, at=NOON + timedelta(minutes=20), **args)
    assert events.alert(tick.state, at=NOON + timedelta(minutes=31), **args)


def test_a_booked_case_runs_then_the_room_is_cleaned(city, make_user):
    tick = make_tick(emergency_theatre=0)
    room = OperatingRoom.objects.create(hospital=city, name="OR 1", capabilities=["general"])
    OrBooking.objects.create(
        room=room,
        booked_by=make_user("doctor", email="surgeon@example.com", hospital=city),
        starts_at=NOON,
        ends_at=NOON + timedelta(hours=1),
        procedure="Hernia repair",
    )
    site = site_of(city)
    with clock.at(NOON + timedelta(minutes=5)):
        theatres.step(site, tick, NOON, NOON + timedelta(minutes=5), set())
    room.refresh_from_db()
    assert room.status == OrStatus.IN_USE
    later = NOON + timedelta(hours=2)
    with clock.at(later):
        theatres.step(site, tick, later - timedelta(minutes=5), later, set())
    room.refresh_from_db()
    assert room.status == OrStatus.CLEANING
    with clock.at(later + timedelta(minutes=45)):
        theatres.step(site, tick, later, later + timedelta(minutes=45), set())
    room.refresh_from_db()
    assert room.status == OrStatus.AVAILABLE


def test_staff_clock_in_near_their_start_and_out_after_their_end(city):
    tick = make_tick(absent=0, late=0)
    member = StaffMember.objects.filter(hospital=city).first()
    shift = Shift.objects.create(
        staff=member, hospital=city, starts_at=NOON + timedelta(hours=1), ends_at=NOON + timedelta(hours=7)
    )
    with clock.at(NOON + timedelta(hours=1, minutes=10)):
        staff.step(tick, NOON + timedelta(hours=1), NOON + timedelta(hours=1, minutes=10), [city])
    shift.refresh_from_db()
    assert abs(shift.clocked_in_at - shift.starts_at) <= timedelta(minutes=12)
    end = NOON + timedelta(hours=7, minutes=30)
    with clock.at(end):
        staff.step(tick, end - timedelta(minutes=30), end, [city])
    shift.refresh_from_db()
    assert shift.ends_at <= shift.clocked_out_at <= shift.ends_at + timedelta(minutes=25)
    assert AuditLog.objects.filter(action="shift.clocked_out", target_id=str(shift.pk)).exists()


def test_the_simulation_leaves_a_case_alone_once_a_person_acts_on_it(city, make_user):
    tick = make_tick()
    nurse = make_user("nurse", email="n2@example.com", hospital=city)
    with clock.at(NOON):
        mine = cases.create_case(
            severity="low",
            patient_ref="SIM-1",
            items=[{"type": "bed", "bedType": "icu", "quantity": 1}],
            actor=tick.actor,
            hospital=city,
        )
        theirs = cases.create_case(
            severity="low",
            patient_ref="SIM-2",
            items=[{"type": "bed", "bedType": "icu", "quantity": 1}],
            actor=tick.actor,
            hospital=city,
        )
    bed = Bed.objects.get(label="MA-01")
    Reservation.objects.create(
        request_item=RequestItem.objects.get(request=theirs),
        content_type=ContentType.objects.get_for_model(Bed),
        object_id=bed.pk,
        hospital=city,
        reserved_by=nurse,
        expires_at=NOON + timedelta(hours=1),
    )
    with clock.at(NOON + timedelta(hours=4)):
        cases.resolve_untouched(tick, NOON + timedelta(hours=4))
    assert EmergencyRequest.objects.get(pk=mine.pk).status == "cancelled"
    assert EmergencyRequest.objects.get(pk=theirs.pk).status == "open"


def test_old_visits_events_and_snapshots_are_pruned(city):
    tick = make_tick()
    with clock.at(NOON - timedelta(days=20)):
        old = ed.arrive(
            hospital=city,
            triage=4,
            age_band="18-39",
            sex="F",
            complaint="minor",
            actor=tick.actor,
            rand=tick.rand,
        )
        ErVisit.objects.filter(pk=old.pk).update(status=VisitStatus.LEFT)
        events.log(NOON - timedelta(days=20), "x", "old")
    events.log(NOON, "x", "new")
    engine.prune(NOON)
    assert not ErVisit.objects.filter(pk=old.pk).exists()
    assert list(SimEvent.objects.values_list("message", flat=True)) == ["new"]


def test_the_wait_estimate_names_what_made_it_longer():
    calm = estimate(
        Inputs(
            doctors=2, doctors_rostered=2, nurses=4, nurses_rostered=4, beds=10, beds_free=8, usual_per_day=70
        )
    )
    assert calm.minutes == 10 and calm.status == "accepting"
    short = estimate(
        Inputs(
            waiting={3: 6, 5: 4},
            doctors=1,
            doctors_rostered=2,
            nurses=4,
            nurses_rostered=4,
            beds=10,
            beds_free=0,
            boarding=3,
            arrivals_last_hour=6,
            usual_per_day=70,
        )
    )
    assert short.minutes > calm.minutes
    effects = {f["key"]: f["minutes"] for f in short.factors}
    assert effects["doctors"] > 0 and effects["queue"] > 0
    assert short.factors[0]["minutes"] == max(effects.values())


def test_the_system_user_cannot_sign_in():
    user = system_user()
    assert not user.is_active and not user.has_usable_password()
    assert system_user().pk == user.pk
