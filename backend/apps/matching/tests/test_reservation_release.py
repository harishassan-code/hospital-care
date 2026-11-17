"""Story #43: releasing a hold, the expiry sweep, the hold setting and the management command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from apps.audit.models import AuditLog
from apps.blood.models import UnitStatus
from apps.equipment.models import EquipmentStatus
from apps.hospitals.models import BedStatus
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.reservations import ReservationNotHeld, release, release_expired, reserve
from apps.operating_rooms.models import OrStatus
from apps.resources.services import change_status
from config.settings import positive_int_env

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


def reserve_one(here, actor, need=None, resource=None):
    """Reserve one resource for a new case; returns (hold, resource)."""
    resource = resource or unit(here, "A+")
    emergency = case(here, need or blood_need("A+"))
    [made] = reserve(emergency.items.get(), hospital=here, quantity=1, actor=actor)
    return made, resource


def run_out(reservations, minutes=1):
    Reservation.objects.filter(pk__in=[r.pk for r in reservations]).update(
        expires_at=timezone.now() - timedelta(minutes=minutes)
    )


# ── Release ────────────────────────────────────────────────────────────────────────────────────


def test_release_frees_the_resource_and_ends_the_hold_with_a_reason(here, nurse):
    made, stock = reserve_one(here, nurse)

    released = release(made, actor=nurse, reason="Released by staff")

    assert status_of(stock) == UnitStatus.AVAILABLE
    released.refresh_from_db()
    assert released.status == ReservationStatus.RELEASED
    assert released.ended_at is not None
    assert released.end_reason == "Released by staff"
    assert AuditLog.objects.filter(action="reservation.released", target_id=str(made.pk)).exists()
    assert AuditLog.objects.filter(action="bloodunit.status_changed", target_id=str(stock.pk)).exists()


@pytest.mark.parametrize(
    ("make", "need", "freed"),
    [
        (lambda h: unit(h, "A+"), blood_need("A+"), UnitStatus.AVAILABLE),
        (lambda h: bed(h), bed_need(), BedStatus.FREE),
        (lambda h: equipment(h), equipment_need(), EquipmentStatus.AVAILABLE),
        (lambda h: room(h), room_need(), OrStatus.AVAILABLE),
    ],
)
def test_release_returns_each_resource_type_to_its_free_status(here, nurse, make, need, freed):
    stock = make(here)
    emergency = case(here, need)
    [made] = reserve(emergency.items.get(), hospital=here, quantity=1, actor=nurse)

    release(made, actor=nurse, reason="Released by staff")

    assert status_of(stock) == freed


@pytest.mark.parametrize(
    "ended", [ReservationStatus.RELEASED, ReservationStatus.EXPIRED, ReservationStatus.ALLOCATED]
)
def test_a_hold_that_is_not_held_cannot_be_released_and_changes_nothing(here, nurse, ended):
    stock = unit(here, "A+", status=UnitStatus.RESERVED)
    made = hold(case(here, blood_need("A+")).items.get(), stock, hospital=here, actor=nurse, status=ended)

    with pytest.raises(ReservationNotHeld):
        release(made, actor=nurse, reason="Released by staff")

    made.refresh_from_db()
    assert made.status == ended
    assert status_of(stock) == UnitStatus.RESERVED


def test_a_released_resource_can_be_held_again_by_another_case(here, nurse):
    made, stock = reserve_one(here, nurse)
    release(made, actor=nurse, reason="Released by staff")

    [again] = reserve(case(here, blood_need("A+")).items.get(), hospital=here, quantity=1, actor=nurse)

    assert again.object_id == stock.pk
    assert status_of(stock) == UnitStatus.RESERVED
    assert Reservation.objects.filter(object_id=stock.pk).count() == 2


def test_a_resource_that_has_moved_on_ends_the_hold_and_is_left_where_it_is(here, nurse):
    made, stock = reserve_one(here, nurse)
    # As allocation (#45) would: only reservation code may move a held unit.
    change_status(stock, "issue", actor=nurse, reason="Given to the patient", held_ok=True)

    release(made, actor=nurse, reason="Released by staff")

    made.refresh_from_db()
    assert made.status == ReservationStatus.RELEASED
    assert status_of(stock) == UnitStatus.ISSUED


# ── Expiry ─────────────────────────────────────────────────────────────────────────────────────


def test_expiry_releases_holds_that_have_run_out_and_returns_their_resources(here, nurse):
    first, stock_a = reserve_one(here, nurse)
    second, stock_b = reserve_one(here, nurse)
    later = timezone.now() + timedelta(minutes=31)

    released = release_expired(now=later)

    assert released == 2
    for made, stock in ((first, stock_a), (second, stock_b)):
        made.refresh_from_db()
        assert made.status == ReservationStatus.EXPIRED
        assert made.ended_at == later
        assert made.end_reason == "Hold expired"
        assert status_of(stock) == UnitStatus.AVAILABLE
    expired_log = AuditLog.objects.get(action="reservation.expired", target_id=str(first.pk))
    assert expired_log.actor_email == ""  # the system, not a person


def test_expiry_leaves_holds_that_have_not_run_out_alone(here, nurse):
    made, stock = reserve_one(here, nurse)

    assert release_expired(now=timezone.now() + timedelta(minutes=29)) == 0

    made.refresh_from_db()
    assert made.status == ReservationStatus.HELD
    assert status_of(stock) == UnitStatus.RESERVED


@override_settings(RESERVATION_HOLD_MINUTES=5)
def test_the_hold_setting_decides_when_a_new_hold_runs_out(here, nurse):
    made, _ = reserve_one(here, nurse)
    made.refresh_from_db()
    start = made.created_at

    assert release_expired(now=start + timedelta(minutes=4)) == 0
    assert release_expired(now=start + timedelta(minutes=6)) == 1


def test_changing_the_setting_does_not_move_a_hold_already_made(here, nurse):
    with override_settings(RESERVATION_HOLD_MINUTES=30):
        made, _ = reserve_one(here, nurse)
    with override_settings(RESERVATION_HOLD_MINUTES=1):
        assert release_expired(now=made.created_at + timedelta(minutes=5)) == 0


def test_the_sweep_is_idempotent(here, nurse):
    reserve_one(here, nurse)
    later = timezone.now() + timedelta(minutes=31)

    assert release_expired(now=later) == 1
    assert release_expired(now=later) == 0


def test_a_released_hold_is_not_expired_afterwards(here, nurse):
    made, _ = reserve_one(here, nurse)
    release(made, actor=nurse, reason="Released by staff")

    assert release_expired(now=timezone.now() + timedelta(minutes=31)) == 0
    made.refresh_from_db()
    assert made.status == ReservationStatus.RELEASED


def test_expiry_of_a_resource_that_has_moved_on_ends_the_hold_only(here, nurse):
    made, stock = reserve_one(here, nurse)
    # As allocation (#45) would: only reservation code may move a held unit.
    change_status(stock, "issue", actor=nurse, reason="Given to the patient", held_ok=True)

    assert release_expired(now=timezone.now() + timedelta(minutes=31)) == 1

    made.refresh_from_db()
    assert made.status == ReservationStatus.EXPIRED
    assert status_of(stock) == UnitStatus.ISSUED


# ── The setting, and the command ───────────────────────────────────────────────────────────────


def test_the_hold_setting_defaults_to_thirty_minutes(monkeypatch):
    monkeypatch.delenv("RESERVATION_HOLD_MINUTES", raising=False)

    assert positive_int_env("RESERVATION_HOLD_MINUTES", 30) == 30


@pytest.mark.parametrize("raw", ["0", "-5", "soon", "1.5"])
def test_a_bad_hold_setting_stops_startup_with_a_message_naming_it(monkeypatch, raw):
    monkeypatch.setenv("RESERVATION_HOLD_MINUTES", raw)

    with pytest.raises(
        ImproperlyConfigured, match="RESERVATION_HOLD_MINUTES must be a whole number of 1 or more"
    ):
        positive_int_env("RESERVATION_HOLD_MINUTES", 30)


def test_the_command_releases_expired_holds_and_prints_how_many(here, nurse):
    made, stock = reserve_one(here, nurse)
    run_out([made])
    out = StringIO()

    call_command("release_expired_reservations", stdout=out)

    assert out.getvalue().strip() == "Released 1 expired hold."
    assert status_of(stock) == UnitStatus.AVAILABLE


def test_the_command_says_zero_when_nothing_has_expired(here, nurse):
    reserve_one(here, nurse)
    out = StringIO()

    call_command("release_expired_reservations", stdout=out)

    assert out.getvalue().strip() == "Released 0 expired holds."
