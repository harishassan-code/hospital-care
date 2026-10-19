"""Task 2.0: shared resource lifecycle. Bad moves raise a domain error; changes record who/when/why."""

import pytest
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import BLOOD_UNIT_LIFECYCLE, BloodUnit, UnitStatus
from apps.hospitals.models import BED_LIFECYCLE, Bed, BedStatus, Ward
from apps.resources.models import Resource
from apps.resources.services import change_status
from apps.resources.state_machine import StateMachine, TransitionNotAllowed

B, U = BedStatus, UnitStatus


def test_bed_and_blood_unit_build_on_the_shared_resource_model():
    assert issubclass(Bed, Resource) and issubclass(BloodUnit, Resource)
    for model in (Bed, BloodUnit):
        names = {f.name for f in model._meta.fields}
        assert {"hospital", "storage_location", "status", "status_since"} <= names
        assert isinstance(model.machine, StateMachine)


BED_MOVES = [
    (B.OCCUPIED, "discharge", B.CLEANING),
    (B.CLEANING, "markReady", B.FREE),
    (B.FREE, "reserve", B.RESERVED),
    (B.FREE, "outOfService", B.OUT_OF_SERVICE),
    (B.RESERVED, "cancelReservation", B.FREE),
    (B.OUT_OF_SERVICE, "returnToService", B.CLEANING),
]

UNIT_MOVES = [
    (U.QUARANTINED, "release", U.AVAILABLE),
    (U.AVAILABLE, "reserve", U.RESERVED),
    (U.RESERVED, "cancelReservation", U.AVAILABLE),
    (U.AVAILABLE, "issue", U.ISSUED),
    (U.RESERVED, "issue", U.ISSUED),
    (U.QUARANTINED, "expire", U.EXPIRED),
    (U.AVAILABLE, "expire", U.EXPIRED),
    (U.RESERVED, "expire", U.EXPIRED),
    (U.QUARANTINED, "discard", U.DISCARDED),  # Sprint 3, #18: a screening test failed
]


@pytest.mark.parametrize(
    ("machine", "statuses", "moves"),
    [(BED_LIFECYCLE, BedStatus, BED_MOVES), (BLOOD_UNIT_LIFECYCLE, UnitStatus, UNIT_MOVES)],
    ids=["bed", "blood unit"],
)
def test_every_status_action_pair_is_allowed_or_refused_exactly_as_listed(machine, statuses, moves):
    allowed = {(start, action): end for start, action, end in moves}
    for status in statuses.values:
        for action in machine.actions:
            if (status, action) in allowed:
                assert machine.next(status, action) == allowed[(status, action)]
            else:
                with pytest.raises(TransitionNotAllowed):
                    machine.next(status, action)


def test_terminal_blood_statuses_have_no_way_out():
    for status in (U.ISSUED, U.EXPIRED, U.DISCARDED):
        for action in BLOOD_UNIT_LIFECYCLE.actions:
            with pytest.raises(TransitionNotAllowed):
                BLOOD_UNIT_LIFECYCLE.next(status, action)


def test_refusal_message_is_readable():
    with pytest.raises(TransitionNotAllowed, match="Can't reserve a bed that is occupied."):
        BED_LIFECYCLE.next(B.OCCUPIED, "reserve")


@pytest.mark.django_db
class TestChangeStatus:
    @pytest.fixture
    def bed(self, make_hospital):
        ward = Ward.objects.create(code="icu", name="ICU", kind="Intensive care", hospital=make_hospital())
        return Bed.objects.create(
            ward=ward,
            label="ICU-01",
            status=B.FREE,
            status_since=timezone.now() - timezone.timedelta(hours=3),
        )

    def test_records_who_when_why_and_the_move(self, bed, make_user):
        nurse = make_user(Role.NURSE)
        before = timezone.now()
        change_status(bed, "reserve", actor=nurse, reason="Incoming trauma patient")
        bed.refresh_from_db()
        assert bed.status == B.RESERVED and bed.status_since >= before
        entry = AuditLog.objects.get()
        assert entry.action == "bed.status_changed"
        assert (entry.actor, entry.target_type, entry.target_repr) == (nurse, "hospitals.bed", "ICU-01")
        assert (entry.before, entry.after, entry.reason) == (
            {"status": "free"},
            {"status": "reserved"},
            "Incoming trauma patient",
        )
        assert entry.at >= before

    def test_the_action_is_the_reason_when_none_is_given(self, bed, make_user):
        change_status(bed, "outOfService", actor=make_user(Role.ADMIN))
        assert AuditLog.objects.get().reason == "outOfService"

    def test_a_refused_move_changes_and_records_nothing(self, bed, make_user):
        since = bed.status_since
        with pytest.raises(TransitionNotAllowed):
            change_status(bed, "discharge", actor=make_user(Role.NURSE))
        bed.refresh_from_db()
        assert (bed.status, bed.status_since) == (B.FREE, since)
        assert not AuditLog.objects.exists()

    def test_a_beds_hospital_follows_its_ward(self, bed):
        assert bed.hospital == bed.ward.hospital
