"""Story #49: confirming receipt. Each unit moves to the receiving hospital and is allocated to the case,
the need and the case move on, and the transfer is delivered, all in one transaction. A step that fails
undoes all of it."""

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.emergencies.services import move_case
from apps.matching.models import Allocation, ReservationStatus
from apps.matching.tests.reservation_support import staff
from apps.resources.services import change_status
from apps.transfers.services import TransferConflict, receive

from .transfer_support import holds, reach, scenario, stock_statuses

pytestmark = pytest.mark.django_db


def audited(action):
    return AuditLog.objects.filter(action=action)


def assert_nothing_moved(s, transfer, *, status, stock):
    """The transfer is where it was, every unit is still the supplier's and held, and nothing was
    allocated."""
    transfer.refresh_from_db()
    assert transfer.status == status
    for resource in s.stock:
        resource.refresh_from_db()
        assert resource.hospital == s.supplier
    assert sorted(stock_statuses(s)) == sorted(stock)
    assert all(h.status == ReservationStatus.HELD for h in holds(transfer))
    assert not Allocation.objects.exists()
    s.item.refresh_from_db()
    assert s.item.fulfilled == 0
    s.case.refresh_from_db()
    assert s.case.status == "matching"
    assert not audited("transfer.delivered").exists()
    assert not AuditLog.objects.filter(action__endswith=".transferred").exists()


# ── Receipt ───────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("state", ["dispatched", "inTransit"])
@pytest.mark.parametrize(("kind", "final"), [("blood", "issued"), ("equipment", "inUse")])
def test_receipt_moves_each_unit_to_the_receiver_and_allocates_it_to_the_case(
    make_user, make_hospital, kind, final, state
):
    s = scenario(make_user, make_hospital, kind=kind)
    transfer = reach(s, state)

    delivered = receive(transfer, actor=s.receiver_staff, note="Checked at the bay")

    assert delivered.status == "delivered"
    for resource in s.stock:
        resource.refresh_from_db()
        assert resource.hospital == s.receiver
        assert resource.storage_location is None
        assert resource.location == "Received from Seaview"
        assert resource.status == final
    allocations = Allocation.objects.filter(request=s.case)
    assert allocations.count() == 2
    assert {a.hospital for a in allocations} == {s.supplier}  # the allocation says who supplied it
    assert all(a.allocated_by == s.receiver_staff and a.note == "Checked at the bay" for a in allocations)
    assert all(h.status == ReservationStatus.ALLOCATED for h in holds(transfer))
    s.item.refresh_from_db()
    assert s.item.fulfilled == 2
    s.case.refresh_from_db()
    assert s.case.status == "fulfilled"


def test_each_unit_move_the_allocation_and_the_transfer_are_audited(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "dispatched")

    receive(transfer, actor=s.receiver_staff)

    moves = audited("bloodunit.transferred").order_by("id")
    assert moves.count() == 2
    first = moves.first()
    assert first.before == {"hospital": {"id": s.supplier.pk, "name": "Seaview"}}
    assert first.after == {"hospital": {"id": s.receiver.pk, "name": "CityCare General"}}
    assert first.actor == s.receiver_staff
    assert audited("allocation.created").count() == 2
    assert audited("transfer.delivered").get().actor == s.receiver_staff


def test_a_partly_approved_transfer_fulfils_only_what_it_brought(make_user, make_hospital):
    s = scenario(make_user, make_hospital, need=3, stock=1)
    transfer = reach(s, "dispatched")

    delivered = receive(transfer, actor=s.receiver_staff)

    assert delivered.status == "delivered"
    assert delivered.quantity == 3 and len(holds(delivered)) == 1
    s.item.refresh_from_db()
    assert s.item.fulfilled == 1
    s.case.refresh_from_db()
    assert s.case.status == "partiallyFulfilled"


def test_the_location_is_cut_to_the_field_length(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    s.supplier.name = "S" * 150
    s.supplier.save(update_fields=["name"])
    transfer = reach(s, "dispatched")

    receive(transfer, actor=s.receiver_staff)

    unit = holds(transfer)[0].resource
    unit.refresh_from_db()
    assert unit.location == ("Received from " + "S" * 150)[:100]


# ── A failure undoes the whole receipt ────────────────────────────────────────────────────────────


def test_a_unit_that_expired_on_the_way_undoes_the_whole_receipt(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "dispatched")
    _, second = holds(transfer)  # the first unit moves before the second is refused
    change_status(second.resource, "expire", actor=s.supplier_staff, reason="Expired", held_ok=True)

    with pytest.raises(TransferConflict, match="expired"):
        receive(transfer, actor=s.receiver_staff)

    assert_nothing_moved(s, transfer, status="dispatched", stock=["reserved", "expired"])
    assert holds(transfer)[0].resource.location == "Blood fridge 1"  # the first unit's move was undone


def test_a_case_that_closed_meanwhile_undoes_the_whole_receipt(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "inTransit")
    move_case(s.case, "escalate", note="Waiting", actor=None)
    move_case(s.case, "close", note="Patient moved", actor=None)

    with pytest.raises(TransferConflict, match="closed"):
        receive(transfer, actor=s.receiver_staff)

    s.case.refresh_from_db()
    assert s.case.status == "closed"
    transfer.refresh_from_db()
    assert transfer.status == "inTransit"
    for resource in s.stock:
        resource.refresh_from_db()
        assert resource.hospital == s.supplier and resource.status == "reserved"
    assert [h.status for h in holds(transfer)] == [ReservationStatus.HELD, ReservationStatus.HELD]
    assert not Allocation.objects.exists()
    assert not audited("transfer.delivered").exists()
    assert not AuditLog.objects.filter(action__endswith=".transferred").exists()


# ── Refusals ──────────────────────────────────────────────────────────────────────────────────────


def test_receiving_twice_is_a_conflict_and_changes_nothing(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "delivered")

    with pytest.raises(TransferConflict, match="delivered"):
        receive(transfer, actor=s.receiver_staff)

    assert Allocation.objects.count() == 2


def test_a_transfer_must_be_dispatched_before_it_is_received(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "approved")

    with pytest.raises(TransferConflict, match="approved"):
        receive(transfer, actor=s.receiver_staff)

    transfer.refresh_from_db()
    assert transfer.status == "approved"
    assert stock_statuses(s) == ["reserved", "reserved"]


@pytest.mark.parametrize("kind", ["blood", "equipment"])
def test_only_receiving_staff_who_may_edit_the_resource_can_receive(make_user, make_hospital, kind):
    s = scenario(make_user, make_hospital, kind=kind)
    transfer = reach(s, "dispatched")
    doctor = staff(make_user, s.receiver, Role.DOCTOR)  # view only on blood and equipment
    same_role_at_supplier = staff(make_user, s.supplier, s.receiver_staff.role)  # the wrong hospital

    for who in (doctor, same_role_at_supplier):
        with pytest.raises(PermissionDenied):
            receive(transfer, actor=who)

    transfer.refresh_from_db()
    assert transfer.status == "dispatched"
    assert stock_statuses(s) == ["reserved", "reserved"]
