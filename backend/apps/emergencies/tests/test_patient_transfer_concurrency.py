"""B17 (stories #63 to #65): moves on one case take turns. Runs on PostgreSQL only: the rules rely on row
locks (select_for_update), and SQLite has none, so these tests are skipped there, as the reservation race
tests are.

Each thread has its own connection and waits at a barrier, so all of them move at the same moment. The threads
must see committed data, so the tests use transaction=True. The deterministic versions of these rules (a
double confirm, a second open request, arrival after cancel) run on every backend in
test_patient_transfer_services.py."""

from functools import partial

import pytest
from django.db import connection

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.emergencies.models import EmergencyRequest, PatientTransfer, PatientTransferStatus
from apps.emergencies.patient_transfers import (
    PatientTransferConflict,
    arrive_patient,
    cancel_patient_transfer,
    request_patient_transfer,
)
from apps.hospitals.models import Hospital
from apps.matching.tests.reservation_support import fire_together, unit

from .patient_support import scenario

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        connection.vendor != "postgresql",
        reason="Row locks (select_for_update) are only enforced by PostgreSQL",
    ),
]


def ask_one(case_pk: int, destination_pk: int, actor_pk: int) -> PatientTransfer:
    return request_patient_transfer(
        EmergencyRequest.objects.get(pk=case_pk),
        destination=Hospital.objects.get(pk=destination_pk),
        actor=User.objects.get(pk=actor_pk),
    )


def arrive_one(transfer_pk: int, actor_pk: int) -> PatientTransfer:
    return arrive_patient(PatientTransfer.objects.get(pk=transfer_pk), actor=User.objects.get(pk=actor_pk))


def cancel_one(transfer_pk: int, actor_pk: int) -> PatientTransfer:
    return cancel_patient_transfer(
        PatientTransfer.objects.get(pk=transfer_pk),
        actor=User.objects.get(pk=actor_pk),
        reason="Changed plan",
    )


def winners_and_losers(results):
    winners = [r for r in results if isinstance(r, PatientTransfer)]
    losers = [r for r in results if isinstance(r, BaseException)]
    return winners, losers


def test_two_requests_for_one_case_leave_one_open_transfer(make_hospital, make_user):
    s = scenario(make_user, make_hospital, destination_stock=2)
    other = make_hospital(name="Harbour Clinic")
    unit(other, "A+")
    unit(other, "A+")

    results = fire_together(
        [
            partial(ask_one, s.emergency.pk, s.destination.pk, s.doctor.pk),
            partial(ask_one, s.emergency.pk, other.pk, s.doctor.pk),
        ]
    )

    winners, losers = winners_and_losers(results)
    assert len(winners) == 1, results
    assert len(losers) == 1 and isinstance(losers[0], PatientTransferConflict), results
    assert (
        PatientTransfer.objects.filter(request=s.emergency, status=PatientTransferStatus.REQUESTED).count()
        == 1
    )


def test_an_arrival_and_a_cancel_leave_exactly_one_outcome(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask_one(s.emergency.pk, s.destination.pk, s.doctor.pk)

    results = fire_together(
        [
            partial(arrive_one, transfer.pk, s.receiver.pk),
            partial(cancel_one, transfer.pk, s.doctor.pk),
        ]
    )

    winners, losers = winners_and_losers(results)
    assert len(winners) == 1, results
    assert len(losers) == 1 and isinstance(losers[0], PatientTransferConflict), results
    transfer.refresh_from_db()
    emergency = EmergencyRequest.objects.get(pk=s.emergency.pk)
    if transfer.status == PatientTransferStatus.ARRIVED:
        assert emergency.hospital == s.destination
        assert AuditLog.objects.filter(action="emergencyrequest.hospital_changed").count() == 1
        assert not AuditLog.objects.filter(action="patienttransfer.cancelled").exists()
    else:
        assert transfer.status == PatientTransferStatus.CANCELLED
        assert emergency.hospital == s.sending
        assert not AuditLog.objects.filter(action="emergencyrequest.hospital_changed").exists()


def test_two_confirmations_of_one_arrival_move_the_case_once(make_hospital, make_user):
    s = scenario(make_user, make_hospital)
    transfer = ask_one(s.emergency.pk, s.destination.pk, s.doctor.pk)

    results = fire_together([partial(arrive_one, transfer.pk, s.receiver.pk) for _ in range(2)])

    winners, losers = winners_and_losers(results)
    assert len(winners) == 1, results
    assert len(losers) == 1 and isinstance(losers[0], PatientTransferConflict), results
    assert AuditLog.objects.filter(action="emergencyrequest.hospital_changed").count() == 1
    assert AuditLog.objects.filter(action="patienttransfer.arrived").count() == 1
