"""Story #48: when a case is closed or cancelled, its unfinished transfers are cancelled with it, so the holds
they pinned at the supplier are released instead of staying locked for ever (pinned holds never expire)."""

import pytest

from apps.emergencies.services import apply_case_action
from apps.matching.models import Reservation, ReservationStatus
from apps.resources.state_machine import TransitionNotAllowed

from .transfer_support import holds, reach, scenario, stock_statuses

pytestmark = pytest.mark.django_db


def test_cancelling_the_case_cancels_a_transfer_in_transit_and_frees_the_stock(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "inTransit")

    apply_case_action(s.case.reference, "cancel", note="Patient moved", actor=s.requester)

    transfer.refresh_from_db()
    assert transfer.status == "cancelled"
    assert transfer.history.last().action == "cancel"
    assert stock_statuses(s) == ["available", "available"]
    assert not Reservation.objects.filter(status=ReservationStatus.HELD).exists()


def test_closing_the_case_cancels_what_is_unfinished_and_keeps_what_was_delivered(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    delivered = reach(s, "delivered", quantity=1)  # the case is now partially fulfilled
    approved = reach(s, "approved", quantity=1)
    pinned = holds(approved)[0]

    apply_case_action(s.case.reference, "close", note="Treated with what arrived", actor=s.requester)

    delivered.refresh_from_db()
    approved.refresh_from_db()
    pinned.refresh_from_db()
    assert delivered.status == "delivered"
    assert approved.status == "cancelled"
    assert pinned.status == ReservationStatus.RELEASED
    assert sorted(stock_statuses(s)) == ["available", "issued"]


def test_a_refused_case_move_leaves_its_transfers_alone(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "approved")

    with pytest.raises(TransitionNotAllowed):  # a matching case can't be closed yet
        apply_case_action(s.case.reference, "close", note="Done", actor=s.requester)

    transfer.refresh_from_db()
    assert transfer.status == "approved"
