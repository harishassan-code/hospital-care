"""Story #44: concurrent reservations cannot double-allocate a resource. Runs on PostgreSQL only.

Each thread has its own database connection (Django keeps one per thread) and waits at a barrier, so all of
them reserve at the same moment. The threads must see committed data, so the tests use transaction=True. Row
locks (select_for_update, skip_locked) are what the service relies on, and SQLite has none, so these tests are
skipped there. The database constraint that backs them up on every backend is tested in
test_reservation_constraints.py."""

import threading
from collections.abc import Callable
from functools import partial

import pytest
from django.db import connection

from apps.accounts.models import User
from apps.blood.models import UnitStatus
from apps.emergencies.models import RequestItem
from apps.hospitals.models import Hospital
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.reservations import ReservationUnavailable, reserve

from .reservation_support import blood_need, case, staff, status_of, unit

THREADS = 8

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="Row locks (select_for_update, skip_locked) are only enforced by PostgreSQL",
    ),
]


def reserve_one(item_pk: int, hospital_pk: int, actor_pk: int) -> list[Reservation]:
    """One reservation of one unit, made in the calling thread with its own connection."""
    item = RequestItem.objects.get(pk=item_pk)
    return reserve(
        item,
        hospital=Hospital.objects.get(pk=hospital_pk),
        quantity=1,
        actor=User.objects.get(pk=actor_pk),
    )


def fire_together(attempts: list[Callable[[], object]]) -> list[object]:
    """Run each attempt in its own thread, all released at once. Returns what each one got: its holds, or the
    exception it raised. Each thread closes its own connection when it is done."""
    barrier = threading.Barrier(len(attempts))
    results: list[object] = [None] * len(attempts)

    def run(index: int, attempt: Callable[[], object]) -> None:
        try:
            barrier.wait(timeout=30)
            results[index] = attempt()
        except Exception as exc:  # the test reads what each thread got, so it must not escape the thread
            results[index] = exc
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i, attempt)) for i, attempt in enumerate(attempts)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=120)
    assert not any(thread.is_alive() for thread in threads), "a reservation hung"
    return results


@pytest.mark.parametrize("same_case", [False, True], ids=["eight cases", "one case and need"])
def test_eight_reservations_for_one_unit_leave_exactly_one(make_hospital, make_user, same_case):
    here = make_hospital()
    nurse = staff(make_user, here)
    stock = unit(here, "A+")
    if same_case:
        item_pks = [case(here, blood_need("A+", quantity=1)).items.get().pk] * THREADS
    else:
        item_pks = [case(here, blood_need("A+", quantity=1)).items.get().pk for _ in range(THREADS)]
    attempts = [partial(reserve_one, pk, here.pk, nurse.pk) for pk in item_pks]

    results = fire_together(attempts)

    winners = [r for r in results if isinstance(r, list)]
    losers = [r for r in results if isinstance(r, BaseException)]
    assert len(winners) == 1, results
    assert len(losers) == THREADS - 1, results
    assert all(isinstance(r, ReservationUnavailable) for r in losers), results
    assert Reservation.objects.filter(status=ReservationStatus.HELD).count() == 1
    assert Reservation.objects.filter(object_id=stock.pk).count() == 1
    assert status_of(stock) == UnitStatus.RESERVED


def test_eight_reservations_for_three_units_leave_exactly_three(make_hospital, make_user):
    here = make_hospital()
    nurse = staff(make_user, here)
    stock = [unit(here, "A+") for _ in range(3)]
    item_pks = [case(here, blood_need("A+", quantity=1)).items.get().pk for _ in range(THREADS)]
    attempts = [partial(reserve_one, pk, here.pk, nurse.pk) for pk in item_pks]

    results = fire_together(attempts)

    winners = [r for r in results if isinstance(r, list)]
    losers = [r for r in results if isinstance(r, BaseException)]
    assert len(winners) == 3, results
    assert len(losers) == THREADS - 3, results
    assert all(isinstance(r, ReservationUnavailable) for r in losers), results
    held = Reservation.objects.filter(status=ReservationStatus.HELD)
    assert sorted(held.values_list("object_id", flat=True)) == sorted(s.pk for s in stock)
    assert all(status_of(s) == UnitStatus.RESERVED for s in stock)
