"""Story #48: following a transfer. Every move the lifecycle table allows works and writes one history
entry and one audit record; every other move is refused and changes nothing. Also who may make which move,
and the moves each user is offered."""

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.matching.tests.reservation_support import staff
from apps.transfers.models import TRANSFER_LIFECYCLE, TransferStatus
from apps.transfers.services import (
    TransferConflict,
    actions_for,
    approve,
    cancel,
    dispatch,
    receive,
    reject,
    start_transit,
)

from .transfer_support import reach, scenario, stock_statuses

pytestmark = pytest.mark.django_db

STATES = list(TransferStatus.values)
ACTIONS = ["approve", "reject", "dispatch", "startTransit", "deliver", "cancel"]
MOVES = {
    "approve": lambda transfer, who: approve(transfer, actor=who),
    "reject": lambda transfer, who: reject(transfer, actor=who, reason="Not now"),
    "dispatch": lambda transfer, who: dispatch(transfer, actor=who),
    "startTransit": lambda transfer, who: start_transit(transfer, actor=who),
    "deliver": lambda transfer, who: receive(transfer, actor=who),
    "cancel": lambda transfer, who: cancel(transfer, actor=who, reason="Changed plans"),
}
# The moves each status offers, for each party (the blood scenario: a blood bank at each hospital, a nurse
# asks).
OFFERED = {
    "requested": {"supplier": ["approve", "reject"], "requester": ["cancel"], "receiver": []},
    "approved": {"supplier": ["dispatch"], "requester": ["cancel"], "receiver": []},
    "dispatched": {"supplier": ["startTransit"], "requester": ["cancel"], "receiver": ["deliver"]},
    "inTransit": {"supplier": [], "requester": ["cancel"], "receiver": ["deliver"]},
    "delivered": {"supplier": [], "requester": [], "receiver": []},
    "rejected": {"supplier": [], "requester": [], "receiver": []},
    "cancelled": {"supplier": [], "requester": [], "receiver": []},
}


@pytest.fixture
def admin(make_user):
    return make_user(Role.ADMIN)


@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("action", ACTIONS)
def test_every_move_in_the_table_works_and_every_other_move_is_refused(
    make_user, make_hospital, admin, state, action
):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, state)
    history_before = transfer.history.count()

    if (state, action) in TRANSFER_LIFECYCLE.transitions:
        moved = MOVES[action](transfer, admin)
        assert moved.status == TRANSFER_LIFECYCLE.transitions[(state, action)]
        assert transfer.history.count() == history_before + 1
        last = transfer.history.last()
        assert (last.from_status, last.action, last.actor) == (state, action, admin)
    else:
        with pytest.raises(TransferConflict):
            MOVES[action](transfer, admin)
        transfer.refresh_from_db()
        assert transfer.status == state
        assert transfer.history.count() == history_before


def test_the_history_is_kept_oldest_first_with_who_and_when(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "delivered")

    rows = list(transfer.history.all())
    assert [r.action for r in rows] == ["request", "approve", "dispatch", "startTransit", "deliver"]
    assert [r.to_status for r in rows] == ["requested", "approved", "dispatched", "inTransit", "delivered"]
    assert [r.actor for r in rows] == [
        s.requester,
        s.supplier_staff,
        s.supplier_staff,
        s.supplier_staff,
        s.receiver_staff,
    ]
    assert all(r.at is not None for r in rows)
    assert all(earlier.at <= later.at for earlier, later in zip(rows, rows[1:], strict=False))


def test_each_move_writes_one_audit_record(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "delivered")

    audited = AuditLog.objects.filter(target_type="transfers.transfer", target_id=str(transfer.pk))
    assert list(audited.order_by("id").values_list("action", flat=True)) == [
        "transfer.requested",
        "transfer.approved",
        "transfer.dispatched",
        "transfer.inTransit",
        "transfer.delivered",
    ]


def test_the_supplier_ships_and_the_requester_cannot(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "approved")

    with pytest.raises(PermissionDenied):
        dispatch(transfer, actor=s.requester)
    transfer.refresh_from_db()
    assert transfer.status == "approved"

    dispatch(transfer, actor=s.supplier_staff)
    with pytest.raises(PermissionDenied):
        start_transit(transfer, actor=s.requester)
    assert start_transit(transfer, actor=s.supplier_staff).status == "inTransit"


def test_the_requester_cancels_in_transit_and_the_units_come_back_to_the_supplier(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "inTransit")

    with pytest.raises(PermissionDenied):
        cancel(transfer, actor=s.supplier_staff)  # the supplier can't cancel what it has approved

    cancelled = cancel(transfer, actor=s.requester, reason="Patient moved")

    assert cancelled.status == "cancelled"
    assert stock_statuses(s) == ["available", "available"]


@pytest.mark.parametrize("state", list(OFFERED))
def test_the_moves_offered_follow_the_status_and_the_side(make_user, make_hospital, admin, state):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, state)
    pharmacist = staff(make_user, s.receiver, Role.PHARMACIST)

    assert actions_for(s.supplier_staff, transfer) == OFFERED[state]["supplier"]
    assert actions_for(s.requester, transfer) == OFFERED[state]["requester"]
    assert actions_for(s.receiver_staff, transfer) == OFFERED[state]["receiver"]
    assert actions_for(pharmacist, transfer) == []
    assert actions_for(admin, transfer) == [
        action for status, action in TRANSFER_LIFECYCLE.transitions if status == state
    ]


def test_a_doctor_at_the_receiver_follows_but_cannot_receive_blood(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "inTransit")
    doctor = staff(make_user, s.receiver, Role.DOCTOR)  # blood: view only

    assert actions_for(doctor, transfer) == ["cancel"]
    with pytest.raises(PermissionDenied):
        receive(transfer, actor=doctor)
    transfer.refresh_from_db()
    assert transfer.status == "inTransit"
