"""B17 (stories #63 to #65) in the API: asking for a patient transfer, the transfer list, the arrival and
cancel actions, and the case detail's `transferFlag` and `patientTransfers`. Shapes match
frontend/src/api/emergencies.ts. Every endpoint has a role matrix or a refusal test; a refused request changes
nothing."""

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import UnitStatus
from apps.emergencies.models import EmergencyRequest, PatientTransfer
from apps.matching.models import ReservationStatus
from apps.matching.reservations import reserve
from apps.matching.tests.reservation_support import blood_need, case, staff, status_of, unit

from .patient_support import scenario, stock_transfer

pytestmark = pytest.mark.django_db

ROW_KEYS = {
    "id",
    "reference",
    "severity",
    "status",
    "from",
    "to",
    "needs",
    "match",
    "requestedBy",
    "requestedAt",
    "arrivedBy",
    "arrivedAt",
    "note",
    "reason",
    "actions",
}
MATCH_KEYS = {
    "rank",
    "hospital",
    "complete",
    "recommended",
    "coverage",
    "coveredCount",
    "totalNeeds",
    "score",
    "distanceKm",
    "travelMinutes",
    "covered",
    "unmet",
}


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def ask_url(reference):
    return reverse("emergency-case-patient-transfer", args=[reference])


def list_url():
    return reverse("patient-transfer-list")


def action_url(transfer):
    return reverse("patient-transfer-action", args=[transfer.pk])


def ask(client, s, destination=None, **body):
    return client.post(
        ask_url(s.emergency.reference),
        {"destinationId": (destination or s.destination).pk, **body},
        format="json",
    )


def act(client, transfer, action, **body):
    return client.post(action_url(transfer), {"action": action, **body}, format="json")


def requested_transfer(s):
    """The sending doctor's request, made through the API."""
    response = ask(as_user(s.doctor), s)
    assert response.status_code == 201, response.json()
    return PatientTransfer.objects.get(pk=response.json()["id"])


def case_url(s):
    return reverse("emergency-case", args=[s.emergency.reference])


@pytest.fixture
def s(make_user, make_hospital):
    return scenario(make_user, make_hospital)


# ── Routes ────────────────────────────────────────────────────────────────────────────────────────


def test_the_list_sits_at_the_api_root_and_the_request_under_the_case():
    assert list_url() == "/api/patient-transfers/"
    assert ask_url("EC-2026-0001") == "/api/emergencies/EC-2026-0001/patient-transfer/"


# ── Access ────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("role", list(Role))
def test_the_list_needs_only_the_emergencies_module_to_be_visible(client_as, role):
    expected = 403 if role == Role.PATIENT else 200

    assert client_as(role).get(list_url()).status_code == expected


def test_signed_out_callers_are_refused(s):
    anonymous = APIClient()

    assert anonymous.get(list_url()).status_code == 403
    assert ask(anonymous, s).status_code == 403


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_roles_without_edit_on_emergencies_cannot_ask(make_user, s, role):
    client = as_user(staff(make_user, s.sending, role))

    assert ask(client, s).status_code == 403
    assert not PatientTransfer.objects.exists()


def test_a_doctor_at_the_destination_cannot_see_or_ask_for_another_hospitals_case(s):
    assert ask(as_user(s.receiver), s).status_code == 404
    assert not PatientTransfer.objects.exists()


def test_an_admin_can_ask_for_any_case(make_user, s):
    response = ask(as_user(make_user(Role.ADMIN)), s)

    assert response.status_code == 201


# ── Asking (#64) ──────────────────────────────────────────────────────────────────────────────────


def test_asking_returns_201_with_the_transfer_and_its_match(s):
    response = ask(as_user(s.doctor), s, note="Cath lab")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == ROW_KEYS
    assert set(body["match"]) == MATCH_KEYS
    assert body["status"] == "requested"
    assert body["reference"] == s.emergency.reference
    assert body["from"] == {"id": s.sending.pk, "name": "CityCare General"}
    assert body["to"] == {"id": s.destination.pk, "name": "Seaview"}
    assert body["needs"] == ["A+ red cells"]
    assert body["note"] == "Cath lab"
    assert body["requestedBy"] == (s.doctor.get_full_name() or s.doctor.email)
    assert body["arrivedBy"] is None and body["arrivedAt"] is None
    assert body["match"]["recommended"] is True
    assert body["actions"] == ["cancel"]
    assert [status_of(stock) for stock in s.stock] == [UnitStatus.AVAILABLE] * len(s.stock)


@pytest.mark.parametrize(
    "body_for",
    [
        lambda s: {"destinationId": 999999},
        lambda s: {"destinationId": s.sending.pk},
        lambda s: {"destinationId": "not-a-number"},
        lambda s: {},
    ],
    ids=["unknown", "own-hospital", "not-a-number", "missing"],
)
def test_a_bad_destination_is_a_400_under_its_field(s, body_for):
    response = as_user(s.doctor).post(ask_url(s.emergency.reference), body_for(s), format="json")

    assert response.status_code == 400
    assert "destinationId" in response.json()
    assert not PatientTransfer.objects.exists()


def test_a_hospital_that_cannot_cover_the_case_is_a_400(make_hospital, s):
    elsewhere = make_hospital(name="Harbour Clinic")

    response = ask(as_user(s.doctor), s, destination=elsewhere)

    assert response.status_code == 400
    assert "destinationId" in response.json()
    assert not PatientTransfer.objects.exists()


def test_a_case_with_nothing_short_is_a_400_with_a_detail(make_user, make_hospital):
    covered = scenario(make_user, make_hospital, local_stock=2)

    response = ask(as_user(covered.doctor), covered)

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Nothing is short")
    assert not PatientTransfer.objects.exists()


def test_a_case_that_cannot_take_stock_is_a_400_with_a_detail(make_user, make_hospital):
    closed = scenario(make_user, make_hospital, status="closed")

    response = ask(as_user(closed.doctor), closed)

    assert response.status_code == 400
    assert response.json()["detail"] == "Can't move a patient for a case that is closed."


def test_a_case_with_no_hospital_is_a_400_for_an_admin(make_user, s):
    orphan = case(None, blood_need("A+", quantity=2))

    response = as_user(make_user(Role.ADMIN)).post(
        ask_url(orphan.reference), {"destinationId": s.destination.pk}, format="json"
    )

    assert response.status_code == 400
    assert "no hospital" in response.json()["detail"]


def test_a_second_open_transfer_for_the_case_is_a_409(s):
    client = as_user(s.doctor)
    assert ask(client, s).status_code == 201

    response = ask(client, s)

    assert response.status_code == 409
    assert "already has a patient transfer" in response.json()["detail"]
    assert PatientTransfer.objects.count() == 1


def test_a_case_you_cannot_see_is_a_404_for_asking(make_user, make_hospital, s):
    outsider = as_user(staff(make_user, make_hospital(name="Harbour Clinic"), Role.DOCTOR))

    assert ask(outsider, s).status_code == 404


# ── The list (#65) ────────────────────────────────────────────────────────────────────────────────


def test_incoming_is_the_receiving_hospitals_and_outgoing_the_sending_ones(s):
    transfer = requested_transfer(s)

    incoming = as_user(s.receiver).get(list_url(), {"direction": "incoming"}).json()
    outgoing = as_user(s.receiver).get(list_url(), {"direction": "outgoing"}).json()
    sender_outgoing = as_user(s.doctor).get(list_url(), {"direction": "outgoing"}).json()
    sender_incoming = as_user(s.doctor).get(list_url(), {"direction": "incoming"}).json()

    assert [row["id"] for row in incoming] == [transfer.pk]
    assert outgoing == []
    assert [row["id"] for row in sender_outgoing] == [transfer.pk]
    assert sender_incoming == []


def test_the_incoming_row_shows_the_patient_without_their_reference_stock_or_holds(s):
    requested_transfer(s)

    row = as_user(s.receiver).get(list_url(), {"direction": "incoming"}).json()[0]

    assert set(row) == ROW_KEYS
    assert "patientRef" not in row
    assert row["severity"] == "critical"
    assert row["needs"] == ["A+ red cells"]
    assert row["from"]["name"] == "CityCare General"
    assert row["actions"] == ["arrive"]


def test_a_third_hospital_sees_no_one_elses_transfers(make_user, make_hospital, s):
    requested_transfer(s)
    stranger = as_user(staff(make_user, make_hospital(name="Harbour Clinic"), Role.DOCTOR))

    assert stranger.get(list_url()).json() == []


def test_an_admin_sees_every_transfer(make_user, s):
    transfer = requested_transfer(s)

    rows = as_user(make_user(Role.ADMIN)).get(list_url()).json()

    assert [row["id"] for row in rows] == [transfer.pk]


def test_the_list_filters_by_status_and_is_newest_first(s):
    first = requested_transfer(s)
    assert act(as_user(s.doctor), first, "cancel", reason="Changed").status_code == 200
    second = requested_transfer(s)
    client = as_user(s.doctor)

    everything = client.get(list_url()).json()
    cancelled = client.get(list_url(), {"status": "cancelled"}).json()
    requested = client.get(list_url(), {"status": "requested"}).json()

    assert [row["id"] for row in everything] == [second.pk, first.pk]
    assert [row["id"] for row in cancelled] == [first.pk]
    assert [row["id"] for row in requested] == [second.pk]


@pytest.mark.parametrize("query", [{"direction": "sideways"}, {"status": "lost"}])
def test_a_bad_direction_or_status_is_a_400(s, query):
    assert as_user(s.doctor).get(list_url(), query).status_code == 400


# ── Arrival (#65) ─────────────────────────────────────────────────────────────────────────────────


def test_arrival_by_the_receiving_doctor_moves_the_case_and_answers_the_transfer(s):
    transfer = requested_transfer(s)

    response = act(as_user(s.receiver), transfer, "arrive")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == ROW_KEYS
    assert body["status"] == "arrived"
    assert body["arrivedBy"] == (s.receiver.get_full_name() or s.receiver.email)
    assert body["arrivedAt"] is not None
    assert body["actions"] == []
    assert EmergencyRequest.objects.get(pk=s.emergency.pk).hospital == s.destination
    assert AuditLog.objects.filter(action="patienttransfer.arrived").count() == 1
    assert AuditLog.objects.filter(action="emergencyrequest.hospital_changed").count() == 1


def test_the_sending_hospital_cannot_confirm_arrival(s):
    transfer = requested_transfer(s)

    response = act(as_user(s.doctor), transfer, "arrive")

    assert response.status_code == 403
    assert PatientTransfer.objects.get(pk=transfer.pk).status == "requested"


def test_a_hospital_in_neither_role_gets_404_for_arrival_and_cancel(make_user, make_hospital, s):
    transfer = requested_transfer(s)
    stranger = as_user(staff(make_user, make_hospital(name="Harbour Clinic"), Role.DOCTOR))

    assert act(stranger, transfer, "arrive").status_code == 404
    assert act(stranger, transfer, "cancel", reason="No").status_code == 404
    assert PatientTransfer.objects.get(pk=transfer.pk).status == "requested"


@pytest.mark.parametrize("role", [Role.BLOOD_BANK, Role.PHARMACIST])
def test_roles_without_edit_on_emergencies_cannot_act_on_a_transfer(make_user, s, role):
    transfer = requested_transfer(s)
    client = as_user(staff(make_user, s.destination, role))

    assert act(client, transfer, "arrive").status_code == 403
    assert PatientTransfer.objects.get(pk=transfer.pk).status == "requested"


def test_a_double_confirm_is_a_409_and_changes_nothing(s):
    transfer = requested_transfer(s)
    client = as_user(s.receiver)
    assert act(client, transfer, "arrive").status_code == 200

    response = act(client, transfer, "arrive")

    assert response.status_code == 409
    assert response.json()["detail"] == "Can't arrive a patient transfer that is arrived."
    assert AuditLog.objects.filter(action="patienttransfer.arrived").count() == 1


def test_confirming_after_a_cancel_is_a_409(s):
    transfer = requested_transfer(s)
    assert act(as_user(s.doctor), transfer, "cancel", reason="Changed").status_code == 200

    response = act(as_user(s.receiver), transfer, "arrive")

    assert response.status_code == 409
    assert EmergencyRequest.objects.get(pk=s.emergency.pk).hospital == s.sending


def test_arrival_while_stock_is_on_its_way_is_a_409_naming_it(make_user, make_hospital, s):
    supplier = make_hospital(name="Harbour Clinic")
    stock = stock_transfer(s, make_user, supplier, status="approved")
    transfer = requested_transfer(s)

    response = act(as_user(s.receiver), transfer, "arrive")

    assert response.status_code == 409
    assert f"#{stock.pk} (approved)" in response.json()["detail"]
    assert PatientTransfer.objects.get(pk=transfer.pk).status == "requested"
    assert EmergencyRequest.objects.get(pk=s.emergency.pk).hospital == s.sending


def test_arrival_releases_the_unallocated_holds_at_the_sending_hospital(s):
    transfer = requested_transfer(s)
    local = unit(s.sending, "A+")
    hold = reserve(s.item, hospital=s.sending, quantity=1, actor=s.nurse)[0]
    assert status_of(local) == UnitStatus.RESERVED

    assert act(as_user(s.receiver), transfer, "arrive").status_code == 200

    hold.refresh_from_db()
    assert hold.status == ReservationStatus.RELEASED
    assert status_of(local) == UnitStatus.AVAILABLE


def test_the_destinations_stock_changing_does_not_block_arrival(s):
    transfer = requested_transfer(s)
    other = case(s.destination, blood_need("A+", quantity=2))
    reserve(other.items.get(), hospital=s.destination, quantity=2, actor=s.receiver)

    assert act(as_user(s.receiver), transfer, "arrive").status_code == 200


def test_an_admin_can_confirm_arrival(make_user, s):
    transfer = requested_transfer(s)

    response = act(as_user(make_user(Role.ADMIN)), transfer, "arrive")

    assert response.status_code == 200


# ── Cancelling by the sending hospital (#65) ──────────────────────────────────────────────────────


def test_the_sending_hospital_cancels_with_a_reason(s):
    transfer = requested_transfer(s)

    response = act(as_user(s.doctor), transfer, "cancel", reason="Patient stable")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["reason"] == "Patient stable"
    assert body["actions"] == []
    assert EmergencyRequest.objects.get(pk=s.emergency.pk).hospital == s.sending


def test_cancelling_without_a_reason_is_a_400_and_changes_nothing(s):
    transfer = requested_transfer(s)

    response = act(as_user(s.doctor), transfer, "cancel", reason="   ")

    assert response.status_code == 400
    assert "reason" in response.json()
    assert PatientTransfer.objects.get(pk=transfer.pk).status == "requested"


def test_the_receiving_hospital_cannot_cancel(s):
    transfer = requested_transfer(s)

    response = act(as_user(s.receiver), transfer, "cancel", reason="No")

    assert response.status_code == 403
    assert PatientTransfer.objects.get(pk=transfer.pk).status == "requested"


def test_an_unknown_action_is_a_400(s):
    transfer = requested_transfer(s)

    assert act(as_user(s.receiver), transfer, "teleport").status_code == 400


@pytest.mark.parametrize("extra", [{}, {"note": "Sent with the arrival"}], ids=["without-note", "with-note"])
def test_arrival_answers_the_same_whether_or_not_a_note_is_sent(s, extra):
    """The action body is {action} only. A `note` key is not part of the contract: it is ignored, and the
    row keeps the note it was requested with."""
    transfer = requested_transfer(s)

    response = act(as_user(s.receiver), transfer, "arrive", **extra)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == ROW_KEYS
    assert body["status"] == "arrived"
    assert body["note"] == ""
    row = PatientTransfer.objects.get(pk=transfer.pk)
    assert (row.status, row.note) == ("arrived", "")


@pytest.mark.parametrize("extra", [{}, {"note": "Sent with the cancel"}], ids=["without-note", "with-note"])
def test_cancel_answers_the_same_whether_or_not_a_note_is_sent(s, extra):
    """Cancel takes a reason and nothing else. A `note` key is ignored: the reason is kept, not the note."""
    transfer = requested_transfer(s)

    response = act(as_user(s.doctor), transfer, "cancel", reason="Patient stable", **extra)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == ROW_KEYS
    assert (body["status"], body["reason"], body["note"]) == ("cancelled", "Patient stable", "")
    row = PatientTransfer.objects.get(pk=transfer.pk)
    assert (row.status, row.reason, row.note) == ("cancelled", "Patient stable", "")


# ── The case (#63 to #65) ─────────────────────────────────────────────────────────────────────────


def test_a_critical_short_case_carries_the_flag_and_its_transfers(s):
    transfer = requested_transfer(s)

    detail = as_user(s.doctor).get(case_url(s)).json()

    assert detail["transferFlag"] is True
    assert [row["id"] for row in detail["patientTransfers"]] == [transfer.pk]
    assert detail["patientTransfers"][0]["actions"] == ["cancel"]


@pytest.mark.parametrize("severity", ["high", "moderate", "low"])
def test_other_severities_do_not_carry_the_flag(make_user, make_hospital, severity):
    other = scenario(make_user, make_hospital, severity=severity)

    detail = as_user(other.doctor).get(case_url(other)).json()

    assert detail["transferFlag"] is False
    assert detail["patientTransfers"] == []


def test_the_destination_sees_the_case_after_arrival_and_the_sender_no_longer_does(s):
    transfer = requested_transfer(s)
    assert as_user(s.receiver).get(case_url(s)).status_code == 404

    assert act(as_user(s.receiver), transfer, "arrive").status_code == 200

    assert as_user(s.doctor).get(case_url(s)).status_code == 404
    arrived = as_user(s.receiver).get(case_url(s)).json()
    assert [row["status"] for row in arrived["patientTransfers"]] == ["arrived"]
    cases = as_user(s.receiver).get(reverse("emergency-cases")).json()
    assert s.emergency.reference in [row["id"] for row in cases]


def test_the_sending_hospital_still_lists_the_arrived_transfer_as_outgoing(s):
    transfer = requested_transfer(s)
    assert act(as_user(s.receiver), transfer, "arrive").status_code == 200

    outgoing = as_user(s.doctor).get(list_url(), {"direction": "outgoing"}).json()

    assert [(row["id"], row["status"]) for row in outgoing] == [(transfer.pk, "arrived")]
    assert outgoing[0]["arrivedAt"] is not None


def test_the_hospital_that_now_holds_the_case_can_send_it_on(make_user, make_hospital):
    # The destination has one unit of the two needed, so the case is still short once the patient is there.
    s = scenario(make_user, make_hospital, destination_stock=1)
    third = make_hospital(name="Harbour Clinic")
    unit(third, "A+")
    transfer = requested_transfer(s)
    assert act(as_user(s.receiver), transfer, "arrive").status_code == 200

    response = as_user(s.receiver).post(
        ask_url(s.emergency.reference), {"destinationId": third.pk}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["from"]["name"] == "Seaview"
