"""Story #47: asking another hospital for stock, the supplier approving or rejecting, and the requester
cancelling. Also the pinned holds a live transfer adds to matching (the expiry sweep, the case page). Moves
after approval are in test_tracking.py, receipt in test_receive.py, and the HTTP shape and permissions in
test_api.py."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.services import move_case
from apps.matching.allocations import allocate
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.reservations import (
    ReservationNotHeld,
    ReservationUnavailable,
    release,
    release_expired,
    reserve,
)
from apps.matching.tests.reservation_support import bed_need, blood_need, case, room_need, staff, unit
from apps.transfers.models import Transfer
from apps.transfers.services import (
    TransferConflict,
    TransferRefused,
    approve,
    cancel,
    reject,
    request_transfer,
)

from .transfer_support import ask, holds, scenario, stock_statuses

pytestmark = pytest.mark.django_db


@pytest.fixture
def s(make_user, make_hospital):
    """Two units of A+ red cells at Seaview, asked for by CityCare General's case (need of 2)."""
    return scenario(make_user, make_hospital)


def audit(action, transfer):
    return AuditLog.objects.filter(
        action=action, target_type="transfers.transfer", target_id=str(transfer.pk)
    )


# ── The model ─────────────────────────────────────────────────────────────────────────────────────


def test_a_transfer_asks_for_a_positive_quantity(s):
    transfer = ask(s)
    with pytest.raises(IntegrityError), transaction.atomic():
        Transfer.objects.filter(pk=transfer.pk).update(quantity=0)


def test_a_hospital_cannot_transfer_to_itself(s):
    transfer = ask(s)
    with pytest.raises(IntegrityError), transaction.atomic():
        Transfer.objects.filter(pk=transfer.pk).update(receiver=s.supplier)


# ── Asking (the request) ──────────────────────────────────────────────────────────────────────────


def test_a_request_records_the_need_both_hospitals_the_quantity_and_who_asked(s):
    transfer = ask(s)

    assert transfer.status == "requested"
    assert transfer.request_item == s.item
    assert (transfer.supplier, transfer.receiver, transfer.quantity) == (s.supplier, s.receiver, 2)
    assert transfer.requested_by == s.requester
    assert transfer.created_at is not None


def test_a_request_reserves_nothing_so_the_supplier_keeps_its_stock(s):
    transfer = ask(s)

    assert holds(transfer) == []
    assert stock_statuses(s) == ["available", "available"]
    s.case.refresh_from_db()
    assert s.case.status == "open"


def test_the_first_history_entry_is_the_request_and_it_is_audited(s):
    transfer = ask(s)

    rows = [(c.from_status, c.to_status, c.action, c.actor) for c in transfer.history.all()]
    assert rows == [("", "requested", "request", s.requester)]
    assert transfer.history.get().at is not None
    assert audit("transfer.requested", transfer).get().actor == s.requester


def test_the_supplier_cannot_be_the_case_hospital(s):
    with pytest.raises(TransferRefused) as refused:
        request_transfer(s.item, supplier=s.receiver, quantity=1, actor=s.requester)

    assert refused.value.field == "supplierId"
    assert Transfer.objects.count() == 0


@pytest.mark.parametrize("need", [bed_need(), room_need()], ids=["bed", "operatingRoom"])
def test_beds_and_operating_rooms_are_not_transferred(s, need):
    emergency = case(s.receiver, need)

    with pytest.raises(TransferRefused, match="Only blood and equipment") as refused:
        request_transfer(emergency.items.get(), supplier=s.supplier, quantity=1, actor=s.requester)

    assert refused.value.field == "itemId"


@pytest.mark.parametrize("status", ["fulfilled", "closed", "cancelled"])
def test_a_case_that_cannot_take_stock_refuses_the_request(make_user, make_hospital, status):
    done = scenario(make_user, make_hospital, status=status)

    with pytest.raises(TransferRefused, match=f"a case that is {status}"):
        ask(done)
    assert Transfer.objects.count() == 0


def test_the_quantity_counts_units_the_need_already_has(make_user, make_hospital):
    s = scenario(make_user, make_hospital, need=4, stock=0)
    s.item.fulfilled = 1
    s.item.save(update_fields=["fulfilled"])

    with pytest.raises(TransferRefused, match="Only 3 more") as refused:
        ask(s, 4)
    assert refused.value.field == "quantity"
    assert ask(s, 3).quantity == 3


def test_the_quantity_counts_holds_at_the_case(make_user, make_hospital):
    s = scenario(make_user, make_hospital, need=4, stock=0)
    unit(s.receiver, "A+")
    reserve(s.item, hospital=s.receiver, quantity=1, actor=s.requester)

    with pytest.raises(TransferRefused, match="Only 3 more"):
        ask(s, 4)
    assert ask(s, 3).quantity == 3


def test_the_quantity_counts_requests_still_waiting_for_an_answer(make_user, make_hospital):
    s = scenario(make_user, make_hospital, need=4, stock=0)
    ask(s, 2)

    with pytest.raises(TransferRefused, match="Only 2 more"):
        ask(s, 3)
    assert ask(s, 2).quantity == 2


def test_a_rejected_request_gives_its_quantity_back(s):
    reject(ask(s, 2), actor=s.supplier_staff, reason="No spare stock")

    assert ask(s, 2).status == "requested"


def test_only_staff_at_the_case_hospital_who_may_edit_emergencies_can_ask(make_user, s):
    blood_bank_here = staff(make_user, s.receiver, Role.BLOOD_BANK)  # emergencies: view only
    doctor_there = staff(make_user, s.supplier, Role.DOCTOR)

    for actor in (blood_bank_here, doctor_there):
        with pytest.raises(PermissionDenied):
            ask(s, actor=actor)
    assert Transfer.objects.count() == 0
    assert ask(s, actor=staff(make_user, None, Role.ADMIN)).status == "requested"


def test_a_case_without_a_hospital_cannot_receive_stock(make_user, s):
    orphan = case(None, blood_need("A+"))

    with pytest.raises(TransferRefused, match="no hospital"):
        request_transfer(
            orphan.items.get(), supplier=s.supplier, quantity=1, actor=staff(make_user, None, Role.ADMIN)
        )


# ── Approving (stock is held at the supplier) ─────────────────────────────────────────────────────


def test_approval_holds_the_units_at_the_supplier_in_one_step(s):
    transfer = approve(ask(s), actor=s.supplier_staff)

    assert transfer.status == "approved"
    held = holds(transfer)
    assert len(held) == 2
    assert all(h.status == ReservationStatus.HELD and h.hospital == s.supplier for h in held)
    assert all(h.request_item == s.item for h in held)
    assert {h.resource for h in held} == set(s.stock)
    assert stock_statuses(s) == ["reserved", "reserved"]
    s.case.refresh_from_db()
    assert s.case.status == "matching"


def test_approval_writes_the_history_and_the_audit_record(s):
    transfer = approve(ask(s), actor=s.supplier_staff, note="Two units set aside")

    rows = [(c.from_status, c.to_status, c.action, c.note, c.actor) for c in transfer.history.all()]
    assert rows[1] == ("requested", "approved", "approve", "Two units set aside", s.supplier_staff)
    assert audit("transfer.approved", transfer).get().actor == s.supplier_staff


def test_units_held_for_a_transfer_are_hidden_from_other_searches(s):
    approve(ask(s), actor=s.supplier_staff)
    other = case(s.supplier, blood_need("A+"))

    with pytest.raises(ReservationUnavailable):
        reserve(other.items.get(), hospital=s.supplier, quantity=1, actor=s.supplier_staff)


def test_partial_approval_holds_what_is_free_and_says_so(make_user, make_hospital):
    s = scenario(make_user, make_hospital, need=2, stock=1)

    transfer = approve(ask(s), actor=s.supplier_staff)

    assert transfer.status == "approved"
    assert transfer.quantity == 2
    assert len(holds(transfer)) == 1


def test_approval_with_nothing_free_is_a_conflict_and_the_request_waits(make_user, make_hospital):
    s = scenario(make_user, make_hospital, stock=0)
    transfer = ask(s)

    with pytest.raises(TransferConflict, match="No matching stock is free"):
        approve(transfer, actor=s.supplier_staff)

    transfer.refresh_from_db()
    assert transfer.status == "requested"
    assert holds(transfer) == []
    assert not audit("transfer.approved", transfer).exists()
    s.case.refresh_from_db()
    assert s.case.status == "open"


def test_approval_is_refused_once_the_case_has_closed(s):
    transfer = ask(s)
    move_case(s.case, "escalate", note="Waiting for a bed", actor=None)
    move_case(s.case, "close", note="Patient moved", actor=None)

    with pytest.raises(TransferConflict, match="closed"):
        approve(transfer, actor=s.supplier_staff)

    transfer.refresh_from_db()
    assert transfer.status == "requested"
    assert holds(transfer) == []


def test_only_the_supplier_staff_who_may_edit_the_resource_can_approve(make_user, s):
    transfer = ask(s)

    with pytest.raises(PermissionDenied):
        approve(transfer, actor=staff(make_user, s.supplier, Role.DOCTOR))  # blood: view only
    with pytest.raises(PermissionDenied):
        approve(transfer, actor=staff(make_user, s.receiver, Role.BLOOD_BANK))  # the other hospital

    transfer.refresh_from_db()
    assert transfer.status == "requested"
    assert stock_statuses(s) == ["available", "available"]


# ── Rejecting ─────────────────────────────────────────────────────────────────────────────────────


def test_rejecting_needs_a_reason(s):
    transfer = ask(s)

    with pytest.raises(TransferRefused, match="Say why") as refused:
        reject(transfer, actor=s.supplier_staff, reason="   ")

    assert refused.value.field == "reason"
    transfer.refresh_from_db()
    assert transfer.status == "requested"
    assert transfer.history.count() == 1


def test_a_rejected_transfer_reserves_nothing_and_keeps_its_reason(s):
    transfer = reject(ask(s), actor=s.supplier_staff, reason="Needed at home")

    assert transfer.status == "rejected"
    assert transfer.reason == "Needed at home"
    assert holds(transfer) == []
    assert stock_statuses(s) == ["available", "available"]
    last = transfer.history.last()
    assert (last.action, last.note, last.actor) == ("reject", "Needed at home", s.supplier_staff)
    assert audit("transfer.rejected", transfer).exists()


# ── Cancelling (by the requester) ─────────────────────────────────────────────────────────────────


def test_cancelling_an_approved_transfer_releases_its_holds(s):
    transfer = approve(ask(s), actor=s.supplier_staff)
    held = holds(transfer)

    cancel(transfer, actor=s.requester, reason="Patient moved")

    transfer.refresh_from_db()
    assert transfer.status == "cancelled"
    assert transfer.reason == "Patient moved"
    assert stock_statuses(s) == ["available", "available"]
    for hold in held:
        hold.refresh_from_db()
        assert hold.status == ReservationStatus.RELEASED
        assert hold.end_reason == f"Transfer #{transfer.pk} cancelled"
    assert audit("transfer.cancelled", transfer).exists()


def test_cancelling_a_request_releases_nothing(s):
    transfer = cancel(ask(s), actor=s.requester)

    assert transfer.status == "cancelled"
    assert stock_statuses(s) == ["available", "available"]


# ── Pinned holds (story #47 changes to matching) ─────────────────────────────────────────────────


def test_pinned_holds_survive_the_expiry_sweep_after_thirty_minutes(s):
    transfer = approve(ask(s), actor=s.supplier_staff)
    later = timezone.now() + timedelta(minutes=31)

    assert release_expired(now=later) == 0

    assert [h.status for h in holds(transfer)] == [ReservationStatus.HELD, ReservationStatus.HELD]
    assert stock_statuses(s) == ["reserved", "reserved"]


def test_a_hold_outside_any_transfer_still_expires(make_user, make_hospital):
    s = scenario(make_user, make_hospital, stock=3)
    transfer = approve(ask(s), actor=s.supplier_staff)
    other = case(s.supplier, blood_need("A+"))
    [free] = reserve(other.items.get(), hospital=s.supplier, quantity=1, actor=s.supplier_staff)

    assert release_expired(now=timezone.now() + timedelta(minutes=31)) == 1

    free.refresh_from_db()
    assert free.status == ReservationStatus.EXPIRED
    assert [h.status for h in holds(transfer)] == [ReservationStatus.HELD, ReservationStatus.HELD]


def test_the_case_page_cannot_release_or_allocate_a_pinned_hold(s):
    transfer = approve(ask(s), actor=s.supplier_staff)
    pinned = holds(transfer)[0]

    with pytest.raises(ReservationNotHeld, match=f"transfer #{transfer.pk}; cancel the transfer instead"):
        release(pinned, actor=s.supplier_staff, reason="Released by staff")
    with pytest.raises(ReservationNotHeld, match="receive the transfer instead"):
        allocate(pinned.pk, actor=s.supplier_staff)

    pinned.refresh_from_db()
    assert pinned.status == ReservationStatus.HELD


def test_a_pinned_hold_past_its_time_is_still_pinned(s):
    transfer = approve(ask(s), actor=s.supplier_staff)
    pinned = holds(transfer)[0]
    Reservation.objects.filter(pk=pinned.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    with pytest.raises(ReservationNotHeld, match="transfer"):
        allocate(pinned.pk, actor=s.supplier_staff)
    assert release_expired() == 0
    pinned.refresh_from_db()
    assert pinned.status == ReservationStatus.HELD


def test_cancelling_leaves_no_pinned_hold_behind(s):
    transfer = approve(ask(s), actor=s.supplier_staff)
    cancel(transfer, actor=s.requester, reason="Changed plans")
    released = holds(transfer)[0]

    assert release_expired(now=timezone.now() + timedelta(minutes=31)) == 0
    released.refresh_from_db()
    assert released.status == ReservationStatus.RELEASED
