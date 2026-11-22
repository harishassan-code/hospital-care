"""Story #52 at the events: each event in the spec reaches the right side and nobody else, and a move that
rolls back sends nothing. The moves are the real ones (case, reservations, transfers), not stand-ins. The
scenario's people: `s.requester` is a nurse at the case's hospital, `s.receiver_staff` a blood bank there,
`s.supplier_staff` a blood bank at the supplier. `people` adds a doctor and an admin at each hospital."""

from datetime import timedelta

import pytest
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role
from apps.emergencies.models import RequestStatusChange
from apps.emergencies.services import apply_case_action, create_case, escalate_overdue, move_case
from apps.matching.reservations import release, release_expired, reserve
from apps.matching.tests.reservation_support import blood_need, case, staff, unit
from apps.notifications.models import Notification
from apps.transfers.services import approve, cancel, start_transit
from apps.transfers.tests.transfer_support import ask, reach, scenario

pytestmark = pytest.mark.django_db

BED = {"type": "bed", "bedType": "icu", "quantity": 1}


@pytest.fixture
def s(make_user, make_hospital):
    """A case at CityCare General asks Seaview for two A+ red cells. Seaview has two free."""
    return scenario(make_user, make_hospital)


@pytest.fixture
def people(s, make_user):
    return {
        "doctor": staff(make_user, s.receiver, Role.DOCTOR),
        "admin": staff(make_user, s.receiver, Role.ADMIN),
        "supplier_doctor": staff(make_user, s.supplier, Role.DOCTOR),
        "supplier_admin": staff(make_user, s.supplier, Role.ADMIN),
    }


def rows(kind=None):
    queryset = Notification.objects.all()
    return queryset.filter(kind=kind) if kind else queryset


def who(kind):
    return set(rows(kind).values_list("user_id", flat=True))


# ── Cases ─────────────────────────────────────────────────────────────────────────────────────────


def test_a_new_critical_case_notifies_the_case_side_except_its_creator(s, people, make_user):
    stranger = staff(make_user, s.supplier, Role.NURSE)

    emergency = create_case(severity="critical", patient_ref="", items=[BED], actor=people["doctor"])

    assert who("case.created") == {s.requester.pk, people["admin"].pk}
    assert stranger.pk not in who("case.created")
    row = rows("case.created").first()
    assert (row.severity, row.link) == ("critical", f"/staff/emergencies/{emergency.reference}")


def test_a_new_case_that_is_not_critical_notifies_nobody(s, people):
    create_case(severity="high", patient_ref="", items=[BED], actor=people["doctor"])
    assert rows().count() == 0


def test_an_escalation_by_hand_notifies_the_case_side(s, people):
    emergency = case(s.receiver, blood_need("A+"), status="open", severity="critical")
    apply_case_action(emergency.reference, "escalate", note="No stock", actor=people["doctor"])

    assert who("case.escalated") == {s.requester.pk, people["admin"].pk}
    assert rows("case.escalated").first().severity == "critical"


def test_an_automatic_escalation_notifies_the_case_side(s, people):
    emergency = case(s.receiver, blood_need("A+"), status="open", severity="critical")
    now = timezone.now()
    RequestStatusChange.objects.create(
        request=emergency, from_status="", to_status="open", action="create", at=now - timedelta(minutes=45)
    )

    assert escalate_overdue(now) == 1

    assert who("case.escalated") == {s.requester.pk, people["doctor"].pk, people["admin"].pk}


def test_a_rolled_back_escalation_sends_nothing(s):
    emergency = case(s.receiver, blood_need("A+"), status="open", severity="critical")
    with transaction.atomic():
        move_case(emergency, "escalate", note="x", actor=None)
        transaction.set_rollback(True)
    assert rows().count() == 0
    emergency.refresh_from_db()
    assert emergency.status == "open"


# ── Reservations ──────────────────────────────────────────────────────────────────────────────────


def test_a_hold_at_the_cases_own_hospital_notifies_its_side_once(s, people):
    emergency = case(s.receiver, blood_need("A+", quantity=2), status="open")
    unit(s.receiver, "A+")
    unit(s.receiver, "A+")

    reserve(emergency.items.get(), hospital=s.receiver, quantity=2, actor=people["doctor"])

    assert who("reservation.created") == {s.requester.pk, people["admin"].pk}
    assert "2 reserved" in rows("reservation.created").first().message


def test_a_hold_released_or_expired_at_the_cases_own_hospital_notifies_its_side(s, people):
    emergency = case(s.receiver, blood_need("A+"), status="open")
    unit(s.receiver, "A+")
    item = emergency.items.get()

    [held] = reserve(item, hospital=s.receiver, quantity=1, actor=s.requester)
    release(held, actor=people["doctor"], reason="Patient moved")
    assert who("reservation.released") == {s.requester.pk, people["admin"].pk}

    [held] = reserve(item, hospital=s.receiver, quantity=1, actor=people["doctor"])
    assert release_expired(now=timezone.now() + timedelta(hours=1)) == 1
    assert who("reservation.expired") == {s.requester.pk, people["doctor"].pk, people["admin"].pk}


def test_a_hold_at_another_hospital_notifies_nobody(s, people):
    """Approving a transfer holds the supplier's units, and cancelling releases them. Neither says anything
    about the hold: the transfer's own events cover it."""
    transfer = ask(s)
    approve(transfer, actor=s.supplier_staff)
    assert rows("reservation.created").count() == 0

    cancel(transfer, actor=s.requester, reason="Patient moved")
    assert rows("reservation.released").count() == 0
    assert rows("reservation.expired").count() == 0
    assert rows("transfer.cancelled").count() > 0  # the transfer's own event did reach people


def test_a_rolled_back_hold_sends_nothing(s, people):
    emergency = case(s.receiver, blood_need("A+"), status="open")
    unit(s.receiver, "A+")
    with transaction.atomic():
        reserve(emergency.items.get(), hospital=s.receiver, quantity=1, actor=people["doctor"])
        transaction.set_rollback(True)
    assert rows().count() == 0


# ── Transfers ─────────────────────────────────────────────────────────────────────────────────────


def test_a_request_is_critical_and_goes_to_the_suppliers_staff_who_can_edit_the_module(s, people, make_user):
    nurse_there = staff(make_user, s.supplier, Role.NURSE)  # no blood edit: not told about blood
    ask(s)

    assert who("transfer.requested") == {s.supplier_staff.pk, people["supplier_admin"].pk}
    assert nurse_there.pk not in who("transfer.requested")
    assert people["supplier_doctor"].pk not in who("transfer.requested")
    row = rows("transfer.requested").first()
    assert (row.severity, row.link) == ("critical", "/staff/transfers")


def test_an_equipment_request_goes_to_the_suppliers_nurses_not_its_blood_bank(make_user, make_hospital):
    s = scenario(make_user, make_hospital, kind="equipment", need=1, stock=1)
    blood_bank = staff(make_user, s.supplier, Role.BLOOD_BANK)
    ask(s)
    assert who("transfer.requested") == {s.supplier_staff.pk}
    assert blood_bank.pk not in who("transfer.requested")


@pytest.mark.parametrize("status", ["approved", "rejected", "dispatched"])
def test_the_suppliers_answer_is_told_to_the_case_side(s, people, status):
    """Approved, rejected and dispatched are the supplier's moves, so the case side hears: the requester and
    the doctor and admin at the receiving hospital, not its blood bank."""
    reach(s, status)
    kind = f"transfer.{status}"
    assert who(kind) == {s.requester.pk, people["doctor"].pk, people["admin"].pk}
    assert rows(kind).first().severity == "info"
    assert s.receiver_staff.pk not in who(kind)


def test_a_cancel_by_the_requester_is_told_to_the_supplier(s, people):
    transfer = ask(s)
    cancel(transfer, actor=s.requester, reason="Patient moved")
    assert who("transfer.cancelled") == {s.supplier_staff.pk, people["supplier_admin"].pk}
    assert rows("transfer.cancelled").first().severity == "info"


def test_a_delivery_is_told_to_the_supplier(s, people):
    reach(s, "delivered")
    assert who("transfer.delivered") == {s.supplier_staff.pk, people["supplier_admin"].pk}
    assert rows("transfer.delivered").first().severity == "info"


def test_starting_transit_tells_nobody(s):
    transfer = reach(s, "dispatched")
    before = Notification.objects.count()
    start_transit(transfer, actor=s.supplier_staff)
    assert Notification.objects.count() == before


def test_a_rolled_back_transfer_move_sends_nothing(s):
    transfer = ask(s)
    before = Notification.objects.count()
    with pytest.raises(RuntimeError), transaction.atomic():
        approve(transfer, actor=s.supplier_staff)
        raise RuntimeError("the surrounding move fails")
    assert Notification.objects.count() == before
    transfer.refresh_from_db()
    assert transfer.status == "requested"


def test_a_hospital_outside_the_move_hears_nothing(s, people, make_user, make_hospital):
    outsider = staff(make_user, make_hospital(name="Northside"), Role.ADMIN)
    reach(s, "delivered")
    assert outsider.pk not in set(Notification.objects.values_list("user_id", flat=True))
