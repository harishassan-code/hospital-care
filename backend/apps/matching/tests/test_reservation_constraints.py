"""Story #44: the database itself refuses double allocation and negative inventory. Each rule is tested at the
database level, with the ORM's own checks out of the way (rows are written directly, or updated with a
query)."""

import pytest
from django.db import IntegrityError, transaction

from apps.emergencies.models import RequestItem
from apps.matching.models import Reservation, ReservationStatus

from .reservation_support import blood_need, case, hold, staff, unit

pytestmark = pytest.mark.django_db


@pytest.fixture
def here(make_hospital):
    return make_hospital()


@pytest.fixture
def actor(make_user, here):
    return staff(make_user, here)


def test_a_second_active_hold_on_the_same_resource_is_refused(here, actor):
    stock = unit(here)
    first = case(here, blood_need())
    second = case(here, blood_need())
    hold(first.items.get(), stock, hospital=here, actor=actor)

    with pytest.raises(IntegrityError), transaction.atomic():
        hold(second.items.get(), stock, hospital=here, actor=actor)

    assert Reservation.objects.filter(object_id=stock.pk).count() == 1


@pytest.mark.parametrize(
    ("existing", "new"),
    [
        (ReservationStatus.HELD, ReservationStatus.HELD),
        (ReservationStatus.HELD, ReservationStatus.ALLOCATED),
        (ReservationStatus.ALLOCATED, ReservationStatus.HELD),
        (ReservationStatus.ALLOCATED, ReservationStatus.ALLOCATED),
    ],
)
def test_held_and_allocated_both_count_as_active(here, actor, existing, new):
    stock = unit(here)
    hold(case(here, blood_need()).items.get(), stock, hospital=here, actor=actor, status=existing)

    with pytest.raises(IntegrityError), transaction.atomic():
        hold(case(here, blood_need()).items.get(), stock, hospital=here, actor=actor, status=new)


@pytest.mark.parametrize("ended", [ReservationStatus.RELEASED, ReservationStatus.EXPIRED])
def test_a_released_or_expired_hold_does_not_block_a_new_hold_on_the_same_resource(here, actor, ended):
    stock = unit(here)
    hold(case(here, blood_need()).items.get(), stock, hospital=here, actor=actor, status=ended)

    new = hold(case(here, blood_need()).items.get(), stock, hospital=here, actor=actor)

    assert new.status == ReservationStatus.HELD
    assert Reservation.objects.filter(object_id=stock.pk).count() == 2


def test_a_hold_on_a_different_resource_is_not_a_conflict(here, actor):
    first, second = unit(here), unit(here)
    hold(case(here, blood_need()).items.get(), first, hospital=here, actor=actor)

    hold(case(here, blood_need()).items.get(), second, hospital=here, actor=actor)

    assert Reservation.objects.filter(status=ReservationStatus.HELD).count() == 2


def test_fulfilled_below_zero_is_refused_by_the_database(here):
    item = case(here, blood_need(quantity=3)).items.get()

    with pytest.raises(IntegrityError), transaction.atomic():
        RequestItem.objects.filter(pk=item.pk).update(fulfilled=-1)


def test_fulfilled_above_quantity_is_refused_by_the_database(here):
    item = case(here, blood_need(quantity=3)).items.get()

    with pytest.raises(IntegrityError), transaction.atomic():
        RequestItem.objects.filter(pk=item.pk).update(fulfilled=4)


@pytest.mark.parametrize("fulfilled", [0, 3])
def test_fulfilled_at_either_bound_is_allowed(here, fulfilled):
    item = case(here, blood_need(quantity=3)).items.get()

    RequestItem.objects.filter(pk=item.pk).update(fulfilled=fulfilled)

    item.refresh_from_db()
    assert item.fulfilled == fulfilled
