"""Stories #45 and #46: allocating a held resource. Each type's resource reaches its final state, the hold
becomes an allocation, the case moves on, and one failure changes nothing."""

from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import UnitStatus
from apps.emergencies.models import EmergencyRequest, RequestStatusChange
from apps.emergencies.services import move_case
from apps.equipment.models import EquipmentStatus
from apps.hospitals.models import BedStatus
from apps.hospitals.services import apply_bed_action
from apps.matching import allocations
from apps.matching.allocations import AllocationRefused, allocate, allocate_many
from apps.matching.models import Allocation, Reservation, ReservationStatus
from apps.matching.reservations import ReservationNotHeld, release, reserve
from apps.operating_rooms.models import OrStatus
from apps.resources.state_machine import TransitionNotAllowed

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
def bloodbank(make_user, here):
    return staff(make_user, here, Role.BLOOD_BANK)


@pytest.fixture
def nurse(make_user, here):
    return staff(make_user, here, Role.NURSE)


def first_item(emergency):
    return emergency.items.order_by("id").first()


def reserved_hold(emergency, actor, quantity=1):
    """Hold the case's first need through the real reservation service."""
    return reserve(first_item(emergency), hospital=emergency.hospital, quantity=quantity, actor=actor)


def moves(emergency):
    return list(emergency.history.order_by("id").values_list("action", flat=True))


def case_status(emergency) -> str:
    emergency.refresh_from_db()
    return emergency.status


def allocation_audits():
    return AuditLog.objects.filter(action="allocation.created", target_type="matching.allocation")


# Each type: how to make its resource, the need it answers, who may allocate it, and its final status.
KINDS = [
    pytest.param(lambda h: unit(h, "A+"), blood_need("A+"), Role.BLOOD_BANK, UnitStatus.ISSUED, id="blood"),
    pytest.param(lambda h: bed(h), bed_need(), Role.NURSE, BedStatus.OCCUPIED, id="bed"),
    pytest.param(
        lambda h: equipment(h), equipment_need(), Role.NURSE, EquipmentStatus.IN_USE, id="equipment"
    ),
    pytest.param(lambda h: room(h), room_need(), Role.NURSE, OrStatus.IN_USE, id="operatingRoom"),
]


@pytest.mark.parametrize(("make_resource", "need", "role", "final"), KINDS)
def test_allocate_moves_each_type_to_its_final_state_and_records_it(
    make_user, here, make_resource, need, role, final
):
    resource = make_resource(here)
    actor = staff(make_user, here, role)
    emergency = case(here, need)
    (made,) = reserved_hold(emergency, actor)
    assert status_of(resource) == "reserved"

    allocation = allocate(made.pk, actor=actor, note="Handed over at the ward")

    assert status_of(resource) == final
    made.refresh_from_db()
    assert made.status == ReservationStatus.ALLOCATED
    assert made.ended_at is not None and made.end_reason == "Allocated"
    assert isinstance(allocation, Allocation)
    assert allocation.reservation_id == made.pk
    assert allocation.request == emergency
    assert allocation.request_item == first_item(emergency)
    assert allocation.resource == resource
    assert allocation.content_type == ContentType.objects.get_for_model(resource)
    assert allocation.hospital == here
    assert allocation.allocated_by == actor
    assert allocation.note == "Handed over at the ward"
    assert first_item(emergency).fulfilled == 1
    assert allocation_audits().filter(target_id=str(allocation.pk), actor=actor).exists()


def test_a_reserved_bed_is_admitted_with_no_patient_recorded(make_user, here, nurse):
    ward_bed = bed(here)
    emergency = case(here, bed_need())
    (made,) = reserved_hold(emergency, nurse)

    allocate(made.pk, actor=nurse)

    ward_bed.refresh_from_db()
    assert ward_bed.status == BedStatus.OCCUPIED
    assert ward_bed.admitted_at is not None
    assert ward_bed.patient_initials == "" and ward_bed.patient_age is None and ward_bed.patient_sex == ""


def test_a_bed_held_for_a_case_cannot_be_admitted_by_hand(here, nurse):
    ward_bed = bed(here)
    emergency = case(here, bed_need())
    reserved_hold(emergency, nurse)

    with pytest.raises(TransitionNotAllowed):
        apply_bed_action(ward_bed.label, "admit", actor=nurse)
    assert status_of(ward_bed) == BedStatus.RESERVED


def test_a_bed_reserved_by_hand_is_admitted_from_the_bed_board(here, nurse):
    ward_bed = bed(here, status=BedStatus.RESERVED)

    apply_bed_action(ward_bed.label, "admit", actor=nurse)

    ward_bed.refresh_from_db()
    assert ward_bed.status == BedStatus.OCCUPIED and ward_bed.admitted_at is not None


# ── The case moves on ────────────────────────────────────────────────────────────────────────────


def test_the_first_allocation_partially_fulfils_and_the_last_fulfils(bloodbank, here):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    first, second = reserved_hold(emergency, bloodbank, quantity=2)

    allocate(first.pk, actor=bloodbank)
    assert case_status(emergency) == "partiallyFulfilled"
    item = first_item(emergency)
    item.refresh_from_db()
    assert (item.fulfilled, item.quantity) == (1, 2)

    allocate(second.pk, actor=bloodbank)
    assert case_status(emergency) == "fulfilled"
    assert moves(emergency) == ["startMatching", "partiallyFulfil", "fulfil"]


def test_a_partly_allocated_case_stays_partial_until_every_need_is_full(bloodbank, here):
    unit(here, "A+")
    unit(here, "O-")
    emergency = case(here, blood_need("A+"), blood_need("O-"))
    a_plus = reserved_hold(emergency, bloodbank)[0]
    o_minus = reserve(emergency.items.order_by("id")[1], hospital=here, quantity=1, actor=bloodbank)[0]

    allocate(a_plus.pk, actor=bloodbank)
    assert case_status(emergency) == "partiallyFulfilled"
    allocate(o_minus.pk, actor=bloodbank)
    assert case_status(emergency) == "fulfilled"


def test_an_escalated_case_resumes_matching_before_it_fulfils(bloodbank, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"), status="escalated")
    (made,) = reserved_hold(emergency, bloodbank)

    allocate(made.pk, actor=bloodbank)

    assert case_status(emergency) == "fulfilled"
    assert moves(emergency) == ["resumeMatching", "fulfil"]


def test_an_open_case_starts_matching_before_it_is_partly_fulfilled(bloodbank, here):
    resource = unit(here, "A+", status=UnitStatus.RESERVED)
    emergency = case(here, blood_need("A+", quantity=2), status="open")
    made = hold(first_item(emergency), resource, hospital=here, actor=bloodbank)

    allocate(made.pk, actor=bloodbank)

    assert case_status(emergency) == "partiallyFulfilled"
    assert moves(emergency) == ["startMatching", "partiallyFulfil"]


def test_the_case_moves_are_system_moves_with_a_note(bloodbank, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, bloodbank)

    allocate(made.pk, actor=bloodbank)

    changes = RequestStatusChange.objects.filter(request=emergency)
    assert changes.exists()
    assert all(change.actor is None for change in changes)
    assert changes.get(action="fulfil").note == "Every need allocated"


@pytest.mark.parametrize("status", ["closed", "cancelled", "fulfilled"])
def test_a_case_that_is_closed_cancelled_or_fulfilled_takes_no_allocation(bloodbank, here, status):
    resource = unit(here, "A+", status=UnitStatus.RESERVED)
    emergency = case(here, blood_need("A+"), status=status)
    made = hold(first_item(emergency), resource, hospital=here, actor=bloodbank)

    with pytest.raises(AllocationRefused):
        allocate(made.pk, actor=bloodbank)

    assert status_of(resource) == UnitStatus.RESERVED
    assert status_of(made) == ReservationStatus.HELD
    assert case_status(emergency) == status


# ── One transaction ──────────────────────────────────────────────────────────────────────────────


def test_a_failure_after_the_resource_move_changes_nothing(bloodbank, here, monkeypatch):
    resource = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, bloodbank)

    def fail(*args, **kwargs):
        raise RuntimeError("the case could not be moved")

    monkeypatch.setattr(allocations, "move_case", fail)
    with pytest.raises(RuntimeError):
        allocate(made.pk, actor=bloodbank)

    assert status_of(resource) == UnitStatus.RESERVED
    assert status_of(made) == ReservationStatus.HELD
    assert first_item(emergency).fulfilled == 0
    assert not Allocation.objects.exists()
    assert not allocation_audits().exists()
    assert case_status(emergency) == "matching"


# ── Holds that can't be allocated ────────────────────────────────────────────────────────────────


def test_an_expired_hold_is_refused(bloodbank, here):
    resource = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, bloodbank)
    Reservation.objects.filter(pk=made.pk).update(expires_at=timezone.now() - timedelta(minutes=1))

    with pytest.raises(ReservationNotHeld, match="run out"):
        allocate(made.pk, actor=bloodbank)
    assert status_of(resource) == UnitStatus.RESERVED


def test_a_released_hold_is_refused(bloodbank, here):
    resource = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, bloodbank)
    release(made, actor=bloodbank, reason="Not needed")

    with pytest.raises(ReservationNotHeld, match="released"):
        allocate(made.pk, actor=bloodbank)
    assert status_of(resource) == UnitStatus.AVAILABLE


def test_allocating_the_same_hold_twice_is_refused(bloodbank, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    (made,) = reserved_hold(emergency, bloodbank)
    allocate(made.pk, actor=bloodbank)

    with pytest.raises(ReservationNotHeld, match="already allocated"):
        allocate(made.pk, actor=bloodbank)
    assert first_item(emergency).fulfilled == 1
    assert Allocation.objects.count() == 1


# ── Who may allocate ─────────────────────────────────────────────────────────────────────────────


def test_a_blood_bank_user_allocates_blood_but_not_a_bed(make_user, here, bloodbank):
    ward_bed = bed(here)
    emergency = case(here, bed_need())
    (made,) = reserved_hold(emergency, staff(make_user, here, Role.NURSE))

    with pytest.raises(PermissionDenied):
        allocate(made.pk, actor=bloodbank)
    assert status_of(ward_bed) == BedStatus.RESERVED
    assert status_of(made) == ReservationStatus.HELD


def test_a_doctor_who_can_only_view_blood_cannot_allocate_it(make_user, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, staff(make_user, here, Role.BLOOD_BANK))

    with pytest.raises(PermissionDenied):
        allocate(made.pk, actor=staff(make_user, here, Role.DOCTOR))


def test_another_hospitals_stock_is_refused_for_a_non_admin(make_user, make_hospital, here):
    there = make_hospital(name="Elsewhere General")
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, staff(make_user, here, Role.BLOOD_BANK))

    with pytest.raises(PermissionDenied):
        allocate(made.pk, actor=staff(make_user, there, Role.BLOOD_BANK))


def test_an_admin_allocates_a_hold_at_any_hospital(make_user, make_hospital, here):
    there = make_hospital(name="Elsewhere General")
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, staff(make_user, here, Role.BLOOD_BANK))

    allocation = allocate(made.pk, actor=staff(make_user, there, Role.ADMIN))

    assert allocation.allocated_by.hospital == there


# ── Several at once ──────────────────────────────────────────────────────────────────────────────


def test_allocate_many_allocates_every_hold_in_the_order_asked(bloodbank, here):
    unit(here, "A+")
    unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    holds = reserved_hold(emergency, bloodbank, quantity=2)

    result = allocate_many([holds[1].pk, holds[0].pk], actor=bloodbank)

    assert [a.reservation_id for a in result] == [holds[1].pk, holds[0].pk]
    assert first_item(emergency).fulfilled == 2
    assert case_status(emergency) == "fulfilled"


def test_allocate_many_is_all_or_nothing(bloodbank, here):
    first_unit = unit(here, "A+")
    second_unit = unit(here, "A+")
    emergency = case(here, blood_need("A+", quantity=2))
    holds = reserved_hold(emergency, bloodbank, quantity=2)
    release(holds[1], actor=bloodbank, reason="Not needed")

    with pytest.raises(ReservationNotHeld):
        allocate_many([holds[0].pk, holds[1].pk], actor=bloodbank)

    assert status_of(first_unit) == UnitStatus.RESERVED
    assert status_of(second_unit) == UnitStatus.AVAILABLE
    assert status_of(holds[0]) == ReservationStatus.HELD
    assert first_item(emergency).fulfilled == 0
    assert not Allocation.objects.exists()
    assert case_status(emergency) == "matching"


def test_allocate_many_refuses_an_unknown_reservation_and_changes_nothing(bloodbank, here):
    resource = unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, bloodbank)

    with pytest.raises(Reservation.DoesNotExist):
        allocate_many([made.pk, made.pk + 1000], actor=bloodbank)
    assert status_of(resource) == UnitStatus.RESERVED


# ── Permanent ────────────────────────────────────────────────────────────────────────────────────


def test_an_allocation_cannot_be_deleted_under_its_hold_or_its_case(bloodbank, here):
    from django.db.models import ProtectedError

    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, bloodbank)
    allocate(made.pk, actor=bloodbank)

    with pytest.raises(ProtectedError):
        Reservation.objects.get(pk=made.pk).delete()
    with pytest.raises(ProtectedError):
        EmergencyRequest.objects.get(pk=emergency.pk).delete()
    assert Allocation.objects.count() == 1


def test_moving_a_case_after_allocation_keeps_the_allocation(bloodbank, here):
    unit(here, "A+")
    emergency = case(here, blood_need("A+"))
    (made,) = reserved_hold(emergency, bloodbank)
    allocate(made.pk, actor=bloodbank)
    emergency.refresh_from_db()

    move_case(emergency, "close", note="Patient transferred", actor=bloodbank)

    assert Allocation.objects.filter(request=emergency).count() == 1
