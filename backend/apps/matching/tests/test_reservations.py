"""Story #43: reserving matched stock for a case, atomically. Release and expiry are in
test_reservation_release.py."""

from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.blood.models import UnitStatus
from apps.emergencies.models import RequestStatusChange
from apps.equipment.models import EquipmentStatus
from apps.hospitals.models import BedStatus
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.reservations import ReservationUnavailable, reserve
from apps.operating_rooms.models import OrStatus

from .reservation_support import (
    bed,
    bed_need,
    blood_need,
    case,
    equipment,
    equipment_need,
    hold,
    room,
    room_need,
    staff,
    status_of,
    unit,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def here(make_hospital):
    return make_hospital()


@pytest.fixture
def nurse(make_user, here):
    return staff(make_user, here)


def reserve_first(emergency, quantity, actor):
    """Reserve for the case's first need, at the case's own hospital."""
    item = emergency.items.order_by("id").first()
    return reserve(item, hospital=emergency.hospital, quantity=quantity, actor=actor)


def reserved_ids(holds):
    return [hold.object_id for hold in holds]


# ── Which resources are picked, and in what order ──────────────────────────────────────────────


def test_blood_is_picked_by_donor_rank_then_earliest_expiry(here, nurse):
    """For A+ red cells the donors rank A+ (0), A- (1), O+ (2), O- (3). Rank comes before expiry, so the A-
    unit that expires soonest still comes after both A+ units, and the O- unit that expires first comes
    last."""
    exact_late = unit(here, "A+", expires_in_days=10)
    exact_soon = unit(here, "A+", expires_in_days=3)
    negative_soon = unit(here, "A-", expires_in_days=0.5)
    unit(here, "O-", expires_in_days=0.1)
    emergency = case(here, blood_need("A+", quantity=3))

    holds = reserve_first(emergency, 3, nurse)

    assert reserved_ids(holds) == [exact_soon.pk, exact_late.pk, negative_soon.pk]


def test_other_hospitals_stock_is_never_reserved_here(make_hospital, here, nurse):
    there = make_hospital(name="Elsewhere")
    unit(there, "A+")
    emergency = case(here, blood_need("A+"))

    with pytest.raises(ReservationUnavailable):
        reserve_first(emergency, 1, nurse)


def test_expired_units_are_not_reserved(here, nurse):
    unit(here, "A+", expires_in_days=-1)
    emergency = case(here, blood_need("A+"))

    with pytest.raises(ReservationUnavailable):
        reserve_first(emergency, 1, nurse)


@pytest.mark.parametrize(
    ("kind", "make", "need", "reserved"),
    [
        ("blood", lambda h: unit(h, "A+"), blood_need("A+"), UnitStatus.RESERVED),
        ("bed", lambda h: bed(h), bed_need(), BedStatus.RESERVED),
        ("equipment", lambda h: equipment(h), equipment_need(), EquipmentStatus.RESERVED),
        ("room", lambda h: room(h), room_need(), OrStatus.RESERVED),
    ],
)
def test_each_resource_type_is_held_and_moved_to_its_reserved_status(here, nurse, kind, make, need, reserved):
    resource = make(here)
    emergency = case(here, need)

    [hold_made] = reserve_first(emergency, 1, nurse)

    assert hold_made.object_id == resource.pk
    assert hold_made.status == ReservationStatus.HELD
    assert status_of(resource) == reserved


# ── The hold itself ────────────────────────────────────────────────────────────────────────────


@override_settings(RESERVATION_HOLD_MINUTES=45)
def test_each_hold_expires_the_configured_number_of_minutes_after_it_is_made(here, nurse):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    before = timezone.now()

    [hold_made] = reserve_first(emergency, 1, nurse)

    after = timezone.now()
    assert before + timedelta(minutes=45) <= hold_made.expires_at <= after + timedelta(minutes=45)


def test_a_reservation_records_who_made_it_and_the_hospital_it_comes_from(here, nurse):
    stock = unit(here, "A+")
    emergency = case(here, blood_need("A+"))

    [hold_made] = reserve_first(emergency, 1, nurse)

    assert hold_made.reserved_by == nurse
    assert hold_made.hospital == here
    assert hold_made.request_item == emergency.items.get()
    assert hold_made.resource == stock


def test_reserving_writes_an_audit_record_for_the_hold_and_for_the_status_change(here, nurse):
    stock = unit(here, "A+")
    emergency = case(here, blood_need("A+"))

    [hold_made] = reserve_first(emergency, 1, nurse)

    created = AuditLog.objects.get(action="reservation.created")
    assert created.target_type == "matching.reservation"
    assert created.target_id == str(hold_made.pk)
    assert created.actor_email == nurse.email
    assert AuditLog.objects.filter(action="bloodunit.status_changed", target_id=str(stock.pk)).exists()


# ── The case ───────────────────────────────────────────────────────────────────────────────────


def test_an_open_case_moves_to_matching_as_a_system_move_with_a_timeline_entry(here, nurse):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"), status="open")

    reserve_first(emergency, 1, nurse)

    emergency.refresh_from_db()
    assert emergency.status == "matching"
    entry = emergency.history.get(action="startMatching")
    assert entry.actor is None
    assert (entry.from_status, entry.to_status) == ("open", "matching")


def test_a_case_already_matching_keeps_its_status_and_gets_no_new_entry(here, nurse):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"), status="matching")
    before = RequestStatusChange.objects.filter(request=emergency).count()

    reserve_first(emergency, 1, nurse)

    emergency.refresh_from_db()
    assert emergency.status == "matching"
    assert RequestStatusChange.objects.filter(request=emergency).count() == before


@pytest.mark.parametrize("status", ["fulfilled", "closed", "cancelled"])
def test_a_case_that_is_finished_cannot_take_stock(here, nurse, status):
    stock = unit(here, "A+")
    emergency = case(here, blood_need("A+"), status=status)

    with pytest.raises(ReservationUnavailable):
        reserve_first(emergency, 1, nurse)

    assert status_of(stock) == UnitStatus.AVAILABLE
    assert not Reservation.objects.exists()


def test_an_escalated_case_can_still_take_stock(here, nurse):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"), status="escalated")

    [hold_made] = reserve_first(emergency, 1, nurse)

    assert hold_made.status == ReservationStatus.HELD
    emergency.refresh_from_db()
    assert emergency.status == "escalated"


def test_a_case_without_a_hospital_has_no_local_stock_to_reserve(here, nurse):
    stock = unit(here, "A+")
    emergency = case(None, blood_need("A+"))

    with pytest.raises(ReservationUnavailable, match="no hospital"):
        reserve(emergency.items.get(), hospital=None, quantity=1, actor=nurse)

    assert status_of(stock) == UnitStatus.AVAILABLE


# ── Partial stock, nothing free, and the quantity guard ────────────────────────────────────────


def test_partial_stock_reserves_what_is_there_and_returns_how_many(here, nurse):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=5))

    holds = reserve_first(emergency, 5, nurse)

    assert len(holds) == 2


def test_nothing_free_is_refused_and_changes_nothing(here, nurse):
    stock = unit(here, "A+", status=UnitStatus.RESERVED)  # already held by something else, with no hold row
    emergency = case(here, blood_need("A+"))

    with pytest.raises(ReservationUnavailable, match="No matching stock"):
        reserve_first(emergency, 1, nurse)

    assert status_of(stock) == UnitStatus.RESERVED
    assert not Reservation.objects.exists()
    emergency.refresh_from_db()
    assert emergency.status == "open"


@pytest.mark.parametrize(
    ("fulfilled", "prior_holds", "asked", "allowed"),
    [
        (0, 0, 3, True),  # the whole need
        (1, 0, 2, True),  # what the fulfilled count leaves
        (1, 0, 3, False),  # more than the fulfilled count leaves
        (0, 2, 2, False),  # two of the three are already held
        (0, 2, 1, True),  # the one that is left
        (2, 1, 1, False),  # nothing is left
    ],
)
def test_no_more_than_the_need_has_left_can_be_reserved(here, nurse, fulfilled, prior_holds, asked, allowed):
    emergency = case(here, blood_need("A+", quantity=3, fulfilled=fulfilled))
    item = emergency.items.get()
    for _ in range(prior_holds):
        hold(item, unit(here, "A+"), hospital=here, actor=nurse)
    for _ in range(5):
        unit(here, "A+")
    holds_before = Reservation.objects.filter(request_item=item, status=ReservationStatus.HELD).count()

    if allowed:
        assert len(reserve_first(emergency, asked, nurse)) == asked
    else:
        with pytest.raises(ReservationUnavailable, match="more can be reserved"):
            reserve_first(emergency, asked, nurse)
        assert (
            Reservation.objects.filter(request_item=item, status=ReservationStatus.HELD).count()
            == holds_before
        )


def test_a_resource_with_an_active_hold_is_never_picked_even_if_its_status_says_free(here, nurse):
    """The status and the hold table disagree (after a manual cancel, say): the hold table still wins."""
    stock = unit(here, "A+")
    hold(case(here, blood_need("A+")).items.get(), stock, hospital=here, actor=nurse)
    emergency = case(here, blood_need("A+"))

    with pytest.raises(ReservationUnavailable):
        reserve_first(emergency, 1, nurse)

    assert Reservation.objects.filter(object_id=stock.pk).count() == 1
