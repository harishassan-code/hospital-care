"""Story #51: ambulance dispatch and trip tracking (B05). An available ambulance from the supplying
hospital carries an approved transfer through its steps (depart, arrive, complete). The API, the rules, the
guards on the transfer, the rollback, and the audit trail."""

import threading

import pytest
from django.db import IntegrityError, connection, transaction
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.ambulances import services
from apps.ambulances.models import Ambulance, Trip
from apps.ambulances.services import dispatch_trip, step_trip, trip_eta_minutes
from apps.audit.models import AuditLog
from apps.emergencies.services import apply_case_action
from apps.hospitals.models import Hospital
from apps.matching.distance import estimated_travel_minutes, hospital_distance
from apps.matching.tests.reservation_support import blood_need, case, staff, unit
from apps.resources.state_machine import TransitionNotAllowed
from apps.transfers.models import Transfer
from apps.transfers.services import (
    TransferConflict,
    approve,
    cancel,
    receive,
    request_transfer,
    start_transit,
)
from apps.transfers.services import dispatch as manual_dispatch
from apps.transfers.tests.transfer_support import reach, scenario

pytestmark = pytest.mark.django_db

TRIP_KEYS = {
    "id",
    "transferId",
    "status",
    "ambulance",
    "etaMinutes",
    "dispatchedBy",
    "dispatchedAt",
    "departedAt",
    "arrivedAt",
    "completedAt",
    "actions",
}


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def van(hospital, identifier="AMB-01", type_="advanced", status="available"):
    return Ambulance.objects.create(hospital=hospital, identifier=identifier, type=type_, status=status)


def dispatch_api(client, transfer, ambulance):
    return client.post(
        reverse("transfer-trips", args=[transfer.pk]), {"ambulance": ambulance.pk}, format="json"
    )


def step_api(client, trip, action):
    return client.post(reverse("trip-action", args=[trip.pk]), {"action": action}, format="json")


def audit_actions():
    return list(AuditLog.objects.order_by("id").values_list("action", flat=True))


def trip_of(transfer):
    return Trip.objects.get(transfer=transfer)


def fresh(obj):  # reload a row so the test reads what the database holds
    obj.refresh_from_db()
    return obj


def dispatched(s, nurse, identifier="AMB-01"):
    """An approved transfer, carried by an ambulance on the road. Returns (transfer, trip, ambulance)."""
    transfer = reach(s, "approved")
    ambulance = van(s.supplier, identifier)
    trip = dispatch_trip(transfer, ambulance_id=ambulance.pk, actor=s.supplier_nurse)
    return fresh(transfer), trip, fresh(ambulance)


def second_transfer(s):
    """A second approved transfer from the same supplier, for another case, to compete for one van."""
    other = case(s.receiver, blood_need("A+", quantity=1), status="open")
    unit(s.supplier, "A+")
    item = other.items.get()
    transfer = request_transfer(item, supplier=s.supplier, quantity=1, actor=s.requester)
    return approve(transfer, actor=s.supplier_staff)


@pytest.fixture
def s(make_user, make_hospital):
    """Blood at CityCare General (the receiver) from Seaview (the supplier), with the supplier's nurse who may
    send the ambulances. Seaview is about 11 km north, so the ETA is not zero."""
    scenario_ = scenario(make_user, make_hospital)
    Hospital.objects.filter(pk=scenario_.supplier.pk).update(latitude="24.960700", longitude="67.001100")
    scenario_.supplier.refresh_from_db()
    scenario_.supplier_nurse = staff(make_user, scenario_.supplier, Role.NURSE)
    return scenario_


@pytest.fixture
def nurse(s):
    return as_user(s.supplier_nurse)


# ── Dispatch (story #51: dispatch) ────────────────────────────────────────────────────────────────


def test_the_supplier_nurse_dispatches_an_available_ambulance_and_gets_the_trip(s, nurse):
    transfer = reach(s, "approved")
    ambulance = van(s.supplier)

    res = dispatch_api(nurse, transfer, ambulance)

    assert res.status_code == 201
    body = res.json()
    assert set(body) == TRIP_KEYS
    assert body["status"] == "dispatched"
    assert body["transferId"] == transfer.pk
    assert body["ambulance"] == {"id": ambulance.pk, "identifier": "AMB-01", "type": "advanced"}
    assert body["dispatchedBy"] == s.supplier_nurse.email
    assert body["actions"] == ["depart"]
    assert (body["departedAt"], body["arrivedAt"], body["completedAt"]) == (None, None, None)
    assert fresh(transfer).status == "dispatched"
    assert fresh(ambulance).status == "dispatched"
    assert {"transfer.dispatched", "ambulance.status_changed", "trip.dispatched"} <= set(audit_actions())


def test_the_trip_on_the_transfer_is_the_one_just_dispatched(s, nurse):
    transfer = reach(s, "approved")
    res = dispatch_api(nurse, transfer, van(s.supplier))

    shown = as_user(s.requester).get(reverse("transfer-detail", args=[transfer.pk])).json()
    assert shown["trip"] == res.json() | {"actions": []}  # the receiver sees it, and can't step it
    assert shown["etaMinutes"] == res.json()["etaMinutes"]
    assert "dispatchAmbulance" not in shown["actions"]


def test_the_eta_is_the_rounded_route_estimate_and_is_stored_once(s, nurse):
    transfer = reach(s, "approved")
    expected = round(estimated_travel_minutes(hospital_distance(s.supplier, s.receiver)))

    res = dispatch_api(nurse, transfer, van(s.supplier))

    assert res.json()["etaMinutes"] == expected and expected > 0
    # Moving the receiving hospital afterwards doesn't change the ETA already promised.
    Hospital.objects.filter(pk=s.receiver.pk).update(latitude="25.500000", longitude="67.500000")
    assert fresh(trip_of(transfer)).eta_minutes == expected


def test_only_an_approved_transfer_gets_a_trip(s, nurse):
    requested = reach(s, "requested")
    ambulance = van(s.supplier)

    res = dispatch_api(nurse, requested, ambulance)

    assert res.status_code == 409
    assert res.json() == {"detail": "Can't dispatch a transfer that is requested."}
    assert fresh(requested).status == "requested"
    assert fresh(ambulance).status == "available"
    assert not Trip.objects.exists()


def test_a_transfer_that_already_has_a_trip_is_409_and_its_ambulance_is_not_touched(s, nurse):
    transfer, _, carrying = dispatched(s, nurse)
    spare = van(s.supplier, "AMB-02")

    res = dispatch_api(nurse, transfer, spare)

    assert res.status_code == 409
    assert fresh(spare).status == "available"
    assert Trip.objects.filter(transfer=transfer).count() == 1


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("maintenance", "Can't dispatch a vehicle that is in maintenance."),
        ("outOfService", "Can't dispatch a vehicle that is out of service."),
    ],
)
def test_only_an_available_ambulance_can_be_dispatched(s, nurse, status, message):
    transfer = reach(s, "approved")
    ambulance = van(s.supplier, status=status)

    res = dispatch_api(nurse, transfer, ambulance)

    assert res.status_code == 409 and res.json() == {"detail": message}
    assert fresh(transfer).status == "approved"
    assert fresh(ambulance).status == status
    assert not Trip.objects.exists()


def test_an_ambulance_already_on_a_trip_is_409_for_another_transfer(s, nurse):
    _, _, carrying = dispatched(s, nurse)
    other = second_transfer(s)

    res = dispatch_api(nurse, other, carrying)

    assert res.status_code == 409
    assert res.json() == {"detail": "Can't dispatch a vehicle that is on trip."}
    assert fresh(other).status == "approved"
    assert Trip.objects.count() == 1


def test_one_active_trip_per_ambulance_is_also_a_database_constraint(s, nurse):
    _, _, carrying = dispatched(s, nurse)
    other = second_transfer(s)
    with pytest.raises(IntegrityError), transaction.atomic():
        Trip.objects.create(transfer=other, ambulance=carrying, eta_minutes=1, dispatched_by=s.supplier_nurse)


def test_one_active_trip_per_transfer_is_also_a_database_constraint(s, nurse):
    transfer, _, _ = dispatched(s, nurse)
    spare = van(s.supplier, "AMB-02")
    with pytest.raises(IntegrityError), transaction.atomic():
        Trip.objects.create(transfer=transfer, ambulance=spare, eta_minutes=1, dispatched_by=s.supplier_nurse)


def test_an_ambulance_based_elsewhere_is_400_and_nothing_changes(make_user, make_hospital, s):
    admin = as_user(make_user(Role.ADMIN, hospital=s.receiver))  # admins may act at any hospital
    transfer = reach(s, "approved")
    receivers_van = van(s.receiver, "AMB-09")

    res = dispatch_api(admin, transfer, receivers_van)

    assert res.status_code == 400
    assert "ambulance" in res.json()
    assert fresh(transfer).status == "approved"
    assert fresh(receivers_van).status == "available"
    assert not Trip.objects.exists()


def test_an_ambulance_the_user_cannot_see_is_404(s, nurse):
    transfer = reach(s, "approved")
    receivers_van = van(s.receiver, "AMB-09")

    assert dispatch_api(nurse, transfer, receivers_van).status_code == 404
    res = nurse.post(reverse("transfer-trips", args=[transfer.pk]), {"ambulance": 9999}, format="json")
    assert res.status_code == 404


def test_a_missing_ambulance_is_400(s, nurse):
    transfer = reach(s, "approved")
    res = nurse.post(reverse("transfer-trips", args=[transfer.pk]), {}, format="json")
    assert res.status_code == 400 and "ambulance" in res.json()


@pytest.mark.parametrize(
    "who", ["doctor", "blood_bank", "receiver_nurse", "pharmacist", "patient", "anonymous"]
)
def test_roles_that_cannot_send_an_ambulance_get_403_and_nothing_changes(make_user, s, who):
    transfer = reach(s, "approved")
    ambulance = van(s.supplier)
    users = {
        "doctor": make_user(Role.DOCTOR, email="doc@example.com", hospital=s.supplier),
        "blood_bank": make_user(Role.BLOOD_BANK, email="bb@example.com", hospital=s.supplier),
        "receiver_nurse": s.requester,  # edits the case, but the ambulances are the supplier's
        "pharmacist": make_user(Role.PHARMACIST, email="ph@example.com", hospital=s.supplier),
        "patient": make_user(Role.PATIENT, email="pt@example.com"),
    }
    client = APIClient() if who == "anonymous" else as_user(users[who])

    res = dispatch_api(client, transfer, ambulance)

    assert res.status_code == 403
    assert fresh(transfer).status == "approved"
    assert fresh(ambulance).status == "available"


def test_an_admin_may_dispatch_from_any_hospital(make_user, s):
    admin = as_user(make_user(Role.ADMIN, email="admin@example.com"))
    transfer = reach(s, "approved")
    res = dispatch_api(admin, transfer, van(s.supplier))
    assert res.status_code == 201


def test_a_user_with_no_link_to_the_transfer_gets_404(make_user, make_hospital, s):
    outsider = as_user(make_user(Role.NURSE, email="out@example.com", hospital=make_hospital("Northside")))
    transfer = reach(s, "approved")
    res = dispatch_api(outsider, transfer, van(s.supplier))
    assert res.status_code == 404
    assert fresh(transfer).status == "approved"


def test_a_failure_after_both_moves_rolls_the_whole_dispatch_back(s, monkeypatch):
    transfer = reach(s, "approved")
    ambulance = van(s.supplier)
    real_record = services.record

    def fail_on_trip(actor, action, target, **kwargs):
        if action == "trip.dispatched":
            raise RuntimeError("the audit write failed")
        return real_record(actor, action, target, **kwargs)

    monkeypatch.setattr(services, "record", fail_on_trip)
    with pytest.raises(RuntimeError):
        dispatch_trip(transfer, ambulance_id=ambulance.pk, actor=s.supplier_nurse)

    assert fresh(transfer).status == "approved"
    assert fresh(ambulance).status == "available"
    assert not Trip.objects.exists()
    assert not AuditLog.objects.filter(
        action__in=["transfer.dispatched", "ambulance.status_changed"]
    ).exists()


@pytest.mark.skipif(connection.vendor != "postgresql", reason="row locks need PostgreSQL; this runs in CI")
@pytest.mark.django_db(transaction=True)
def test_two_dispatches_of_one_ambulance_at_once_exactly_one_wins(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    nurse = staff(make_user, s.supplier, Role.NURSE)
    first, second = reach(s, "approved"), second_transfer(s)
    ambulance = van(s.supplier)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def worker(transfer_pk):
        try:
            barrier.wait()
            dispatch_trip(Transfer.objects.get(pk=transfer_pk), ambulance_id=ambulance.pk, actor=nurse)
            outcomes.append("won")
        except (TransitionNotAllowed, TransferConflict):
            outcomes.append("refused")
        except Exception as exc:  # anything else must fail the test, not look like a refusal
            outcomes.append(type(exc).__name__)
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(t.pk,)) for t in (first, second)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["refused", "won"]
    assert Trip.objects.count() == 1


# ── Trip steps (story #51: depart, arrive, complete) ──────────────────────────────────────────────


def test_the_trip_walks_depart_arrive_complete_and_the_transfer_follows_the_rules(s, nurse):
    transfer, trip, ambulance = dispatched(s, nurse)

    res = step_api(nurse, trip, "depart")
    assert res.status_code == 200
    assert (res.json()["status"], res.json()["actions"]) == ("enRoute", ["arrive"])
    assert res.json()["departedAt"] is not None
    assert (fresh(transfer).status, fresh(ambulance).status) == ("inTransit", "dispatched")

    res = step_api(nurse, trip, "arrive")
    assert (res.json()["status"], res.json()["actions"]) == ("arrived", ["complete"])
    assert fresh(transfer).status == "inTransit"

    res = step_api(nurse, trip, "complete")
    assert (res.json()["status"], res.json()["actions"]) == ("completed", [])
    assert res.json()["completedAt"] is not None
    # Completing frees the ambulance and does not deliver the transfer: the receiver confirms it (story #49).
    assert (fresh(transfer).status, fresh(ambulance).status) == ("inTransit", "available")


def test_each_step_is_audit_logged_with_the_transfer_and_ambulance_moves(s, nurse):
    _, trip, _ = dispatched(s, nurse)
    for action in ("depart", "arrive", "complete"):
        step_api(nurse, trip, action)

    logged = audit_actions()
    for expected in (
        "trip.dispatched",
        "trip.departed",
        "transfer.inTransit",
        "trip.arrived",
        "trip.completed",
        "ambulance.status_changed",
    ):
        assert expected in logged
    assert logged.index("trip.departed") < logged.index("trip.arrived") < logged.index("trip.completed")


@pytest.mark.parametrize(
    ("walk", "action", "message"),
    [
        ([], "arrive", "Can't arrive a trip that is dispatched."),
        ([], "complete", "Can't complete a trip that is dispatched."),
        (["depart"], "depart", "Can't depart a trip that is en route."),
        (["depart"], "complete", "Can't complete a trip that is en route."),
        (["depart", "arrive", "complete"], "depart", "Can't depart a trip that is completed."),
        (["depart", "arrive", "complete"], "arrive", "Can't arrive a trip that is completed."),
        (["depart", "arrive", "complete"], "complete", "Can't complete a trip that is completed."),
    ],
)
def test_an_out_of_order_step_is_409_and_changes_nothing(s, nurse, walk, action, message):
    transfer, trip, ambulance = dispatched(s, nurse)
    for done in walk:
        step_api(nurse, trip, done)
    before = (fresh(trip).status, fresh(transfer).status, fresh(ambulance).status)

    res = step_api(nurse, trip, action)

    assert res.status_code == 409 and res.json() == {"detail": message}
    assert (fresh(trip).status, fresh(transfer).status, fresh(ambulance).status) == before


def test_an_unknown_step_is_refused_as_a_conflict(s, nurse):
    _, trip, _ = dispatched(s, nurse)
    res = step_api(nurse, trip, "fly")
    assert res.status_code == 409 and res.json() == {"detail": "Can't fly a trip that is dispatched."}
    assert fresh(trip).status == "dispatched"


def test_a_failed_departure_leaves_the_trip_and_the_transfer_where_they_were(s, nurse, monkeypatch):
    transfer, trip, _ = dispatched(s, nurse)
    real_record = services.record

    def fail_on_depart(actor, action, target, **kwargs):
        if action == "trip.departed":
            raise RuntimeError("the audit write failed")
        return real_record(actor, action, target, **kwargs)

    monkeypatch.setattr(services, "record", fail_on_depart)
    with pytest.raises(RuntimeError):
        step_trip(trip, "depart", actor=s.supplier_nurse)

    assert (fresh(trip).status, fresh(transfer).status) == ("dispatched", "dispatched")
    assert not AuditLog.objects.filter(action="transfer.inTransit").exists()


def test_the_receiver_sees_the_trip_but_cannot_step_it(s, nurse):
    _, trip, _ = dispatched(s, nurse)
    receiver = as_user(s.receiver_staff)

    res = step_api(receiver, trip, "depart")

    assert res.status_code == 403
    assert fresh(trip).status == "dispatched"
    shown = receiver.get(reverse("transfer-detail", args=[trip.transfer_id])).json()
    assert shown["trip"]["status"] == "dispatched"
    assert shown["trip"]["actions"] == []


def test_the_supplier_without_ambulance_access_cannot_step_the_trip(s, nurse):
    _, trip, _ = dispatched(s, nurse)
    blood_bank = as_user(s.supplier_staff)  # blood bank at the supplier: transfers only

    assert step_api(blood_bank, trip, "depart").status_code == 403
    assert fresh(trip).status == "dispatched"


def test_a_trip_is_404_to_a_user_who_cannot_see_its_transfer(make_user, make_hospital, s, nurse):
    _, trip, _ = dispatched(s, nurse)
    outsider = as_user(make_user(Role.NURSE, email="out@example.com", hospital=make_hospital("Northside")))
    assert step_api(outsider, trip, "depart").status_code == 404


def test_completing_the_trip_leaves_the_receipt_to_the_receiver(s, nurse):
    transfer, trip, _ = dispatched(s, nurse)
    for action in ("depart", "arrive", "complete"):
        step_trip(trip, action, actor=s.supplier_nurse)

    delivered = receive(fresh(transfer), actor=s.receiver_staff)

    assert delivered.status == "delivered"


# ── Manual moves while a trip is active ───────────────────────────────────────────────────────────


def test_manual_moves_on_a_transfer_with_an_active_trip_are_409(s, nurse):
    transfer, trip, _ = dispatched(s, nurse)

    with pytest.raises(TransferConflict, match="Use the trip's steps"):
        cancel(transfer, actor=s.requester, reason="Patient moved")
    with pytest.raises(TransferConflict, match="Use the trip's steps"):
        receive(transfer, actor=s.receiver_staff)
    # The supplier's own hand-moves (dispatch and start transit) are blocked too, not only the requester's.
    with pytest.raises(TransferConflict, match="Use the trip's steps"):
        manual_dispatch(transfer, actor=s.supplier_staff)
    with pytest.raises(TransferConflict, match="Use the trip's steps"):
        start_transit(transfer, actor=s.supplier_staff)
    assert fresh(transfer).status == "dispatched"
    assert fresh(trip).status == "dispatched"


def test_manual_moves_are_refused_over_the_transfer_api_with_the_trip_message(s, nurse):
    transfer, _, _ = dispatched(s, nurse)
    blood_bank = as_user(s.supplier_staff)
    requester = as_user(s.requester)

    res = blood_bank.post(
        reverse("transfer-action", args=[transfer.pk]), {"action": "startTransit"}, format="json"
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "An ambulance is carrying this transfer. Use the trip's steps instead."
    res = requester.post(reverse("transfer-action", args=[transfer.pk]), {"action": "cancel"}, format="json")
    assert res.status_code == 409
    assert fresh(transfer).status == "dispatched"


def test_no_manual_moves_are_offered_while_the_trip_is_active(s, nurse):
    transfer, _, _ = dispatched(s, nurse)
    for user in (s.supplier_staff, s.requester, s.receiver_staff):
        res = as_user(user).get(reverse("transfer-detail", args=[transfer.pk])).json()
        assert res["actions"] == []


def test_the_manual_moves_come_back_once_the_trip_is_complete(s, nurse):
    transfer, trip, _ = dispatched(s, nurse)
    for action in ("depart", "arrive", "complete"):
        step_trip(trip, action, actor=s.supplier_nurse)

    res = as_user(s.receiver_staff).get(reverse("transfer-detail", args=[transfer.pk])).json()
    assert res["actions"] == ["deliver"]


def test_a_case_that_closes_while_its_trip_is_on_the_road_is_refused(s, nurse):
    transfer, trip, ambulance = dispatched(s, nurse)

    with pytest.raises(TransitionNotAllowed, match="Complete its trip first"):
        apply_case_action(s.case.reference, "cancel", note="Patient moved", actor=s.requester)

    assert fresh(s.case).status == "matching"  # the stock reserved for the transfer moved the case on
    assert (fresh(transfer).status, fresh(trip).status, fresh(ambulance).status) == (
        "dispatched",
        "dispatched",
        "dispatched",
    )


# ── Ambulances and the transfer's offer ───────────────────────────────────────────────────────────


def test_the_transfer_offers_dispatch_to_the_supplier_nurse_only_while_approved(s, nurse):
    transfer = reach(s, "approved")
    url = reverse("transfer-detail", args=[transfer.pk])

    assert "dispatchAmbulance" in as_user(s.supplier_nurse).get(url).json()["actions"]
    # The blood bank at the supplier may move transfers but has no edit on ambulances, so no dispatch.
    assert "dispatchAmbulance" not in as_user(s.supplier_staff).get(url).json()["actions"]
    assert "dispatchAmbulance" not in as_user(s.requester).get(url).json()["actions"]


def test_manual_ambulance_moves_refuse_the_trip_moves(s, nurse):
    ambulance = van(s.supplier)
    url = reverse("ambulance-action", args=[ambulance.pk])

    for action in ("dispatch", "release"):
        res = nurse.post(url, {"action": action}, format="json")
        assert res.status_code == 409
        assert res.json() == {"detail": "A trip moves this vehicle. Use the transfer's trip instead."}
    assert fresh(ambulance).status == "available"


def test_a_vehicle_on_a_trip_cannot_be_moved_by_hand(s, nurse):
    _, _, ambulance = dispatched(s, nurse)
    res = nurse.post(
        reverse("ambulance-action", args=[ambulance.pk]), {"action": "startMaintenance"}, format="json"
    )
    assert res.status_code == 409
    assert res.json() == {"detail": "Can't startMaintenance a vehicle that is on trip."}


def test_the_ambulance_list_shows_the_trip_and_its_status(s, nurse):
    transfer, trip, _ = dispatched(s, nurse)
    url = reverse("ambulance-list")

    listed = nurse.get(url).json()
    assert listed[0]["status"] == "dispatched"
    assert listed[0]["trip"] == {"id": trip.pk, "status": "dispatched", "transferId": transfer.pk}

    assert nurse.get(url, {"status": "available"}).json() == []
    step_trip(trip, "depart", actor=s.supplier_nurse)
    step_trip(trip, "arrive", actor=s.supplier_nurse)
    step_trip(trip, "complete", actor=s.supplier_nurse)
    listed = nurse.get(url).json()
    assert listed[0]["status"] == "available" and listed[0]["trip"] is None


def test_the_ambulance_list_can_be_filtered_by_base_hospital(make_user, make_hospital, s):
    van(s.supplier, "AMB-01")
    van(s.receiver, "AMB-02")
    admin = as_user(make_user(Role.ADMIN, email="admin@example.com"))
    url = reverse("ambulance-list")

    assert [a["identifier"] for a in admin.get(url, {"hospital": s.supplier.pk}).json()] == ["AMB-01"]
    assert len(admin.get(url).json()) == 2


# ── Services used directly (the view just translates) ─────────────────────────────────────────────


def test_dispatch_by_the_service_matches_the_api(s):
    transfer = reach(s, "approved")
    trip = dispatch_trip(transfer, ambulance_id=van(s.supplier).pk, actor=s.supplier_nurse)
    assert trip.status == "dispatched" and trip.eta_minutes == trip_eta_minutes(s.supplier, s.receiver)
    assert fresh(transfer).status == "dispatched"
