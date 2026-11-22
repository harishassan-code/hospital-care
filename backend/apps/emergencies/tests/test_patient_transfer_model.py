"""B17 (stories #63 to #65): the patient transfer row, its lifecycle and the database's own rules. A case
has at most one requested transfer at a time, and a transfer never names the same hospital twice."""

import pytest
from django.db import IntegrityError, transaction

from apps.accounts.models import Role
from apps.emergencies.models import (
    PATIENT_TRANSFER_LIFECYCLE,
    PatientTransfer,
    PatientTransferStatus,
)
from apps.matching.tests.reservation_support import case, staff
from apps.resources.state_machine import TransitionNotAllowed

pytestmark = pytest.mark.django_db

REQUESTED = PatientTransferStatus.REQUESTED
ARRIVED = PatientTransferStatus.ARRIVED
CANCELLED = PatientTransferStatus.CANCELLED


@pytest.fixture
def parties(make_hospital, make_user):
    here = make_hospital(name="CityCare General")
    there = make_hospital(name="Seaview")
    doctor = staff(make_user, here, Role.DOCTOR)
    return here, there, doctor


def transfer_for(emergency, here, there, doctor, **fields):
    return PatientTransfer.objects.create(
        request=emergency,
        from_hospital=here,
        to_hospital=there,
        requested_by=doctor,
        **fields,
    )


@pytest.mark.parametrize(
    ("status", "action", "expected"), [(REQUESTED, "arrive", ARRIVED), (REQUESTED, "cancel", CANCELLED)]
)
def test_the_lifecycle_moves_a_requested_transfer_on(status, action, expected):
    assert PATIENT_TRANSFER_LIFECYCLE.next(status, action) == expected


@pytest.mark.parametrize(
    ("status", "action"),
    [(ARRIVED, "arrive"), (ARRIVED, "cancel"), (CANCELLED, "arrive"), (CANCELLED, "cancel")],
)
def test_arrived_and_cancelled_are_final(status, action):
    with pytest.raises(TransitionNotAllowed, match="patient transfer"):
        PATIENT_TRANSFER_LIFECYCLE.next(status, action)


def test_a_new_transfer_is_requested_with_no_arrival_and_an_empty_snapshot(parties):
    here, there, doctor = parties
    emergency = case(here)

    row = transfer_for(emergency, here, there, doctor, note="Needs the cath lab")

    row.refresh_from_db()
    assert row.status == REQUESTED
    assert row.match == {}
    assert row.arrived_by is None and row.arrived_at is None
    assert row.reason == ""
    assert row.requested_at is not None
    assert str(row) == f"Patient transfer #{row.pk}"


def test_the_database_refuses_a_transfer_to_the_same_hospital(parties):
    here, _, doctor = parties
    emergency = case(here)

    with pytest.raises(IntegrityError), transaction.atomic():
        transfer_for(emergency, here, here, doctor)


def test_the_database_refuses_a_second_open_transfer_for_one_case(parties, make_hospital):
    here, there, doctor = parties
    elsewhere = make_hospital(name="Harbour Clinic")
    emergency = case(here)
    transfer_for(emergency, here, there, doctor)

    with pytest.raises(IntegrityError), transaction.atomic():
        transfer_for(emergency, here, elsewhere, doctor)


def test_a_case_can_be_sent_again_once_its_open_transfer_is_over(parties, make_hospital):
    here, there, doctor = parties
    elsewhere = make_hospital(name="Harbour Clinic")
    emergency = case(here)
    transfer_for(emergency, here, there, doctor, status=CANCELLED)
    transfer_for(emergency, here, elsewhere, doctor, status=ARRIVED)

    transfer_for(emergency, here, there, doctor)

    assert PatientTransfer.objects.filter(request=emergency).count() == 3
    assert PatientTransfer.objects.filter(request=emergency, status=REQUESTED).count() == 1
