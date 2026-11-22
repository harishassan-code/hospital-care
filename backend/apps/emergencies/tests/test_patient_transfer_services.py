"""B17 (stories #63 to #65), the rules: the need check, asking for a move, the sending hospital's cancel, and
the receiving hospital's confirmation of arrival with what it does to the case's stock and history. Each write
is audit-logged, and a refused one changes nothing. The race tests are in
test_patient_transfer_concurrency.py."""

import re

import pytest
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import BloodUnit, UnitStatus
from apps.emergencies.models import EmergencyRequest, PatientTransfer, PatientTransferStatus
from apps.emergencies.patient_transfers import (
    PatientTransferConflict,
    PatientTransferRefused,
    arrive_patient,
    cancel_patient_transfer,
    request_patient_transfer,
    transfer_flag,
)
from apps.emergencies.services import apply_case_action
from apps.matching.allocations import allocate
from apps.matching.models import Reservation, ReservationStatus
from apps.matching.reservations import reserve
from apps.matching.tests.reservation_support import blood_need, case, staff, status_of, unit
from apps.transfers.models import TransferStatus

from .patient_support import scenario, stock_transfer

pytestmark = pytest.mark.django_db

REQUESTED = PatientTransferStatus.REQUESTED
ARRIVED = PatientTransferStatus.ARRIVED
CANCELLED = PatientTransferStatus.CANCELLED


def ask(s, *, destination=None, actor=None, note=""):
    """The sending doctor asks to move the patient to the destination (the scenario's, by default)."""
    return request_patient_transfer(
        s.emergency,
        destination=destination or s.destination,
        note=note,
        actor=actor or s.doctor,
    )


def audit(action, target):
    """The audit rows for one action on one object."""
    return AuditLog.objects.filter(
        action=action, target_type=target._meta.label_lower, target_id=str(target.pk)
    )


def fresh(transfer):
    return PatientTransfer.objects.get(pk=transfer.pk)


def case_now(emergency):
    return EmergencyRequest.objects.get(pk=emergency.pk)


# ── The need check (#63) ──────────────────────────────────────────────────────────────────────────


def test_a_critical_case_short_of_stock_raises_the_flag(make_hospital, make_user):
    s = scenario(make_user, make_hospital)

    assert transfer_flag(s.emergency) is True


@pytest.mark.parametrize("severity", ["high", "moderate", "low"])
def test_other_severities_do_not_raise_the_flag(make_hospital, make_user, severity):
    s = scenario(make_user, make_hospital, severity=severity)

    assert transfer_flag(s.emergency) is False


def test_a_case_covered_here_does_not_raise_the_flag(make_hospital, make_user):
    s = scenario(make_user, make_hospital, local_stock=2)

    assert transfer_flag(s.emergency) is False


def test_stock_held_here_counts_as_local(make_hospital, make_user):
    s = scenario(make_user, make_hospital, local_stock=2)
    reserve(s.item, hospital=s.sending, quantity=2, actor=s.nurse)

    assert transfer_flag(s.emergency) is False


# ── Asking for a move (#64) ───────────────────────────────────────────────────────────────────────


def test_asking_keeps_the_destinations_match_and_reserves_nothing_there(make_hospital, make_user):
    s = scenario(make_user, make_hospital)

    transfer = ask(s, note="  Cath lab  ")

    transfer.refresh_from_db()
    assert transfer.status == REQUESTED
    assert transfer.from_hospital == s.sending
    assert transfer.to_hospital == s.destination
    assert transfer.note == "Cath lab"
    assert transfer.requested_by == s.doctor
    assert transfer.arrived_at is None and transfer.arrived_by is None
    assert transfer.match["rank"] == 1
    assert transfer.match["recommended"] is True
    assert transfer.match["hospital"] == {"id": s.destination.pk, "name": "Seaview"}
    assert transfer.match["covered"] == [{"itemId": s.item.pk, "need": "A+ red cells"}]
    assert transfer.match["unmet"] == []
    assert [status_of(stock) for stock in s.stock] == [UnitStatus.AVAILABLE] * len(s.stock)
    assert Reservation.objects.count() == 0
    assert audit("patienttransfer.requested", transfer).get().actor == s.doctor


def test_the_snapshot_is_kept_when_the_destinations_stock_changes(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)
    for stock in s.stock:
        stock.status = UnitStatus.ISSUED
        stock.save(update_fields=["status"])

    transfer.refresh_from_db()
    assert transfer.match["covered"] == [{"itemId": s.item.pk, "need": "A+ red cells"}]


def test_a_case_with_no_hospital_is_refused(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    admin = make_user(Role.ADMIN)
    orphan = case(None, blood_need("A+", quantity=2))

    with pytest.raises(PatientTransferRefused, match="no hospital"):
        request_patient_transfer(orphan, destination=s.destination, actor=admin)
    assert PatientTransfer.objects.count() == 0


def test_a_case_with_nothing_short_is_refused(make_hospital, make_user):
    s = scenario(make_user, make_hospital, local_stock=2)

    with pytest.raises(PatientTransferRefused, match="Nothing is short"):
        ask(s)
    assert PatientTransfer.objects.count() == 0


@pytest.mark.parametrize("status", ["closed", "cancelled", "fulfilled"])
def test_a_case_that_cannot_take_stock_is_refused(make_hospital, make_user, status):
    s = scenario(make_user, make_hospital, status=status)

    with pytest.raises(PatientTransferRefused, match=f"that is {status}") as refused:
        ask(s)

    assert refused.value.field is None
    assert PatientTransfer.objects.count() == 0


def test_the_case_hospital_cannot_be_the_destination(make_hospital, make_user):
    s = scenario(make_user, make_hospital)

    with pytest.raises(PatientTransferRefused, match="own hospital") as refused:
        ask(s, destination=s.sending)

    assert refused.value.field == "destinationId"


def test_an_inactive_hospital_cannot_be_the_destination(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    s.destination.is_active = False
    s.destination.save(update_fields=["is_active"])

    with pytest.raises(PatientTransferRefused, match="not active") as refused:
        ask(s)

    assert refused.value.field == "destinationId"


def test_a_hospital_that_cannot_cover_the_case_is_not_a_destination(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    elsewhere = make_hospital(name="Harbour Clinic")

    with pytest.raises(PatientTransferRefused, match="can cover this case") as refused:
        ask(s, destination=elsewhere)

    assert refused.value.field == "destinationId"
    assert PatientTransfer.objects.count() == 0


def test_a_second_open_transfer_for_a_case_is_a_conflict(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    ask(s)

    with pytest.raises(PatientTransferConflict, match="already has a patient transfer"):
        ask(s)
    assert PatientTransfer.objects.filter(request=s.emergency).count() == 1


def test_a_case_can_be_sent_again_once_its_open_transfer_is_cancelled(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    first = ask(s)
    cancel_patient_transfer(first, actor=s.doctor, reason="Patient stable")

    second = ask(s)

    assert second.status == REQUESTED
    assert PatientTransfer.objects.filter(request=s.emergency).count() == 2


@pytest.mark.parametrize("who", ["receiver", "pharmacist", "blood_bank", "neighbour"])
def test_only_edit_staff_at_the_case_hospital_can_ask(make_hospital, make_user, who):
    s = scenario(make_user, make_hospital)
    neighbour_hospital = make_hospital(name="Harbour Clinic")
    actor = {
        "receiver": lambda: s.receiver,
        "pharmacist": lambda: staff(make_user, s.sending, Role.PHARMACIST),
        "blood_bank": lambda: s.sending_bank,
        "neighbour": lambda: staff(make_user, neighbour_hospital, Role.DOCTOR),
    }[who]()

    with pytest.raises(PermissionDenied):
        ask(s, actor=actor)
    assert PatientTransfer.objects.count() == 0


def test_an_admin_can_ask_for_any_case(make_hospital, make_user):
    s = scenario(make_user, make_hospital)

    transfer = ask(s, actor=make_user(Role.ADMIN))

    assert transfer.status == REQUESTED


# ── Cancelling by the sending hospital (#65) ──────────────────────────────────────────────────────


def test_the_sending_hospital_cancels_with_a_reason(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)

    cancelled = cancel_patient_transfer(transfer, actor=s.doctor, reason="  Patient stable  ")

    cancelled.refresh_from_db()
    assert cancelled.status == CANCELLED
    assert cancelled.reason == "Patient stable"
    assert cancelled.arrived_at is None
    assert audit("patienttransfer.cancelled", transfer).exists()
    assert case_now(s.emergency).hospital == s.sending


def test_cancelling_needs_a_reason_and_changes_nothing_without_one(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)

    with pytest.raises(PatientTransferRefused, match="Say why") as refused:
        cancel_patient_transfer(transfer, actor=s.doctor, reason="   ")

    assert refused.value.field == "reason"
    assert fresh(transfer).status == REQUESTED


def test_the_receiving_hospital_cannot_cancel(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)

    with pytest.raises(PermissionDenied, match="sending hospital"):
        cancel_patient_transfer(transfer, actor=s.receiver, reason="No")
    assert fresh(transfer).status == REQUESTED


def test_a_cancelled_transfer_cannot_be_cancelled_again(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)
    cancel_patient_transfer(transfer, actor=s.doctor, reason="Changed")

    with pytest.raises(PatientTransferConflict, match="Can't cancel"):
        cancel_patient_transfer(transfer, actor=s.doctor, reason="Again")
    assert len(audit("patienttransfer.cancelled", transfer)) == 1


# ── Arrival (#65) ─────────────────────────────────────────────────────────────────────────────────


def test_arrival_moves_the_case_and_records_who_and_when(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)

    arrived = arrive_patient(transfer, actor=s.receiver)

    arrived.refresh_from_db()
    assert arrived.status == ARRIVED
    assert arrived.arrived_by == s.receiver
    assert arrived.arrived_at is not None
    moved = case_now(s.emergency)
    assert moved.hospital == s.destination
    assert moved.status == "open"
    change = audit("emergencyrequest.hospital_changed", s.emergency).get()
    assert change.before == {"hospital": {"id": s.sending.pk, "name": "CityCare General"}}
    assert change.after == {"hospital": {"id": s.destination.pk, "name": "Seaview"}}
    assert audit("patienttransfer.arrived", transfer).get().actor == s.receiver


def test_arrival_keeps_the_row_as_history(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s, note="Needs the cath lab")

    arrive_patient(transfer, actor=s.receiver)

    row = fresh(transfer)
    assert row.from_hospital == s.sending
    assert row.to_hospital == s.destination
    assert row.requested_by == s.doctor
    assert row.note == "Needs the cath lab"
    assert row.match["covered"] == [{"itemId": s.item.pk, "need": "A+ red cells"}]


def test_arrival_releases_unallocated_holds_and_keeps_allocated_ones(make_hospital, make_user):
    # Three needed, two held here and one of them allocated: one short still, so the patient may move.
    s = scenario(make_user, make_hospital, need=3, local_stock=2, destination_stock=1)
    held = reserve(s.item, hospital=s.sending, quantity=2, actor=s.nurse)
    kept, released = held
    allocate(kept.pk, actor=s.sending_bank)
    transfer = ask(s)

    arrive_patient(transfer, actor=s.receiver)

    released.refresh_from_db()
    kept.refresh_from_db()
    assert released.status == ReservationStatus.RELEASED
    assert released.end_reason == "Patient arrived at Seaview"
    assert kept.status == ReservationStatus.ALLOCATED
    assert BloodUnit.objects.get(pk=kept.object_id).status == UnitStatus.ISSUED
    assert BloodUnit.objects.get(pk=released.object_id).status == UnitStatus.AVAILABLE
    assert audit("reservation.released", released).exists()
    assert not audit("reservation.released", kept).exists()


@pytest.mark.parametrize(
    "status", [TransferStatus.APPROVED, TransferStatus.DISPATCHED, TransferStatus.IN_TRANSIT]
)
def test_arrival_is_refused_while_stock_is_on_its_way_and_names_it(make_hospital, make_user, status):
    s = scenario(make_user, make_hospital)
    supplier = make_hospital(name="Harbour Clinic")
    stock = stock_transfer(s, make_user, supplier, status=status)
    transfer = ask(s)

    with pytest.raises(PatientTransferConflict, match=rf"#{stock.pk} \({re.escape(status.label.lower())}\)"):
        arrive_patient(transfer, actor=s.receiver)

    assert fresh(transfer).status == REQUESTED
    assert case_now(s.emergency).hospital == s.sending
    stock.refresh_from_db()
    assert stock.status == status


def test_arrival_cancels_the_cases_requested_stock_transfers(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    supplier = make_hospital(name="Harbour Clinic")
    stock = stock_transfer(s, make_user, supplier, status="requested")
    transfer = ask(s)

    arrive_patient(transfer, actor=s.receiver)

    stock.refresh_from_db()
    assert stock.status == TransferStatus.CANCELLED
    assert stock.reason == "Patient arrived at Seaview"
    assert audit("transfer.cancelled", stock).exists()
    assert case_now(s.emergency).hospital == s.destination


def test_arrival_does_not_depend_on_the_destinations_stock_any_more(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)
    other_case = case(s.destination, blood_need("A+", quantity=2))
    reserve(other_case.items.get(), hospital=s.destination, quantity=2, actor=s.receiver)

    arrive_patient(transfer, actor=s.receiver)

    assert case_now(s.emergency).hospital == s.destination
    assert fresh(transfer).status == ARRIVED


def test_arrival_goes_through_when_the_destination_is_deactivated_after_the_request(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)
    s.destination.is_active = False
    s.destination.save(update_fields=["is_active"])

    arrive_patient(transfer, actor=s.receiver)

    assert fresh(transfer).status == ARRIVED


def test_a_double_confirm_is_refused_and_changes_nothing(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)
    arrive_patient(transfer, actor=s.receiver)
    first_arrival = fresh(transfer).arrived_at

    with pytest.raises(PatientTransferConflict, match="Can't arrive"):
        arrive_patient(transfer, actor=s.receiver)

    assert fresh(transfer).arrived_at == first_arrival
    assert len(audit("patienttransfer.arrived", transfer)) == 1
    assert len(audit("emergencyrequest.hospital_changed", s.emergency)) == 1


def test_confirming_arrival_after_cancel_is_refused(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)
    cancel_patient_transfer(transfer, actor=s.doctor, reason="Changed")

    with pytest.raises(PatientTransferConflict, match="Can't arrive"):
        arrive_patient(transfer, actor=s.receiver)

    assert case_now(s.emergency).hospital == s.sending


def test_the_sending_hospital_cannot_confirm_arrival(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)

    with pytest.raises(PermissionDenied, match="receiving hospital"):
        arrive_patient(transfer, actor=s.doctor)
    assert fresh(transfer).status == REQUESTED


def test_a_hospital_in_neither_role_cannot_confirm_arrival(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)
    stranger = staff(make_user, make_hospital(name="Harbour Clinic"), Role.DOCTOR)

    with pytest.raises(PermissionDenied):
        arrive_patient(transfer, actor=stranger)
    assert fresh(transfer).status == REQUESTED


def test_an_admin_can_confirm_arrival(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask(s)

    arrive_patient(transfer, actor=make_user(Role.ADMIN))

    assert fresh(transfer).status == ARRIVED


def test_a_moved_case_can_be_sent_on_by_the_hospital_that_now_holds_it(make_hospital, make_user):
    s = scenario(make_user, make_hospital, destination_stock=1)
    third = make_hospital(name="Harbour Clinic")
    unit(third, "A+")
    first = ask(s)
    arrive_patient(first, actor=s.receiver)

    second = request_patient_transfer(s.emergency, destination=third, actor=s.receiver)

    assert second.from_hospital == s.destination
    assert second.to_hospital == third
    assert second.status == REQUESTED
    assert PatientTransfer.objects.filter(request=s.emergency).count() == 2


# ── A case that closes or is cancelled (#65) ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "action", "note"),
    [("open", "cancel", ""), ("partiallyFulfilled", "close", "Patient died before the move")],
)
def test_closing_or_cancelling_the_case_cancels_its_requested_transfer(
    make_hospital, make_user, status, action, note
):
    s = scenario(make_user, make_hospital, status=status)
    transfer = ask(s)

    apply_case_action(s.emergency.reference, action, note=note, actor=s.doctor)

    cancelled = fresh(transfer)
    assert cancelled.status == CANCELLED
    assert cancelled.reason.startswith(f"Case {s.emergency.reference}")
    assert audit("patienttransfer.cancelled", transfer).exists()
    with pytest.raises(PatientTransferConflict):
        arrive_patient(transfer, actor=s.receiver)
    assert case_now(s.emergency).hospital == s.sending
