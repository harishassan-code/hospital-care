"""Story #50 ambulance registry and story #51 dispatch and trip tracking."""

import pytest

from apps.accounts.models import Role
from apps.ambulances.models import Ambulance, Trip
from apps.audit.models import AuditLog
from apps.matching.tests.reservation_support import staff
from apps.transfers.models import Transfer
from apps.transfers.services import cancel, receive
from apps.transfers.tests.transfer_support import reach, scenario

pytestmark = pytest.mark.django_db


def as_user(user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.force_authenticate(user)
    return client


def amb(hospital, identifier="AMB-1", status="available"):
    return Ambulance.objects.create(
        hospital=hospital, identifier=identifier, ambulance_type="als", status=status
    )


# ── Registry (#50) ────────────────────────────────────────────────────────────────────────────────


def test_a_nurse_registers_an_ambulance_at_their_hospital(make_user, make_hospital):
    hospital = make_hospital()
    res = as_user(staff(make_user, hospital, Role.NURSE)).post(
        "/api/ambulances/", {"identifier": "amb-cg-01", "type": "bls", "plate": "KHI-1"}, format="json"
    )
    assert res.status_code == 201
    data = res.json()
    assert (data["identifier"], data["type"], data["status"], data["hospital"]) == (
        "AMB-CG-01",
        "bls",
        "available",
        hospital.name,
    )
    assert AuditLog.objects.filter(action="ambulance.registered").count() == 1


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.BLOOD_BANK, Role.PHARMACIST])
def test_other_roles_cannot_register(client_as, role):
    res = client_as(role).post("/api/ambulances/", {"identifier": "X", "type": "bls"}, format="json")
    assert res.status_code == 403


def test_list_filters_and_own_hospital(make_user, make_hospital):
    mine, other = make_hospital(name="Mine"), make_hospital(name="Other")
    amb(mine, "A1")
    amb(mine, "A2", status="maintenance")
    amb(other, "B1")
    client = as_user(staff(make_user, mine, Role.DOCTOR))
    assert [a["identifier"] for a in client.get("/api/ambulances/").json()] == ["A1", "A2"]
    assert [a["identifier"] for a in client.get("/api/ambulances/?status=available").json()] == ["A1"]


def test_manual_status_changes_follow_the_lifecycle(make_user, make_hospital):
    hospital = make_hospital()
    a = amb(hospital)
    client = as_user(staff(make_user, hospital, Role.NURSE))
    url = f"/api/ambulances/{a.pk}/actions/"
    assert client.post(url, {"action": "startMaintenance"}, format="json").json()["status"] == "maintenance"
    assert client.post(url, {"action": "startMaintenance"}, format="json").status_code == 409
    assert (
        client.post(url, {"action": "startTrip"}, format="json").status_code == 400
    )  # only a trip does that


# ── Dispatch and trips (#51) ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def s(make_user, make_hospital):
    return scenario(make_user, make_hospital)


def dispatch(s, ambulance, user=None):
    transfer = reach(s, "approved")
    res = as_user(user or s.supplier_staff).post(
        "/api/ambulances/trips/", {"transferId": transfer.pk, "ambulanceId": ambulance.pk}, format="json"
    )
    return transfer, res


def test_dispatch_sends_an_available_ambulance_and_moves_the_transfer(s):
    a = amb(s.supplier)
    transfer, res = dispatch(s, a)
    assert res.status_code == 201
    assert res.json()["status"] == "dispatched" and res.json()["etaMinutes"] is not None
    assert Transfer.objects.get(pk=transfer.pk).status == "dispatched"
    assert Ambulance.objects.get(pk=a.pk).status == "onTrip"
    detail = as_user(s.receiver_staff).get(f"/api/transfers/{transfer.pk}/").json()
    assert detail["trip"]["ambulance"]["identifier"] == "AMB-1"


def test_a_busy_ambulance_cant_be_dispatched_and_nothing_moves(s):
    a = amb(s.supplier, status="maintenance")
    transfer, res = dispatch(s, a)
    assert res.status_code == 409
    assert Transfer.objects.get(pk=transfer.pk).status == "approved"
    assert not Trip.objects.exists()


def test_another_hospitals_ambulance_is_refused(s):
    transfer, res = dispatch(s, amb(s.receiver))
    assert res.status_code == 409
    assert Transfer.objects.get(pk=transfer.pk).status == "approved"


def test_trip_runs_en_route_arrived_then_receipt_completes_it(s):
    a = amb(s.supplier)
    transfer, res = dispatch(s, a)
    trip_url = f"/api/ambulances/trips/{res.json()['id']}/actions/"
    client = as_user(s.supplier_staff)
    assert client.post(trip_url, {"action": "enRoute"}, format="json").json()["status"] == "enRoute"
    assert Transfer.objects.get(pk=transfer.pk).status == "inTransit"
    assert client.post(trip_url, {"action": "arrive"}, format="json").json()["status"] == "arrived"
    assert as_user(s.receiver_staff).post(trip_url, {"action": "arrive"}, format="json").status_code == 403

    receive(Transfer.objects.get(pk=transfer.pk), actor=s.receiver_staff)
    assert Trip.objects.get().status == "completed"
    assert Ambulance.objects.get(pk=a.pk).status == "available"


def test_cancelling_the_transfer_cancels_the_trip_and_frees_the_ambulance(s):
    a = amb(s.supplier)
    transfer, _ = dispatch(s, a)
    cancel(Transfer.objects.get(pk=transfer.pk), actor=s.requester, reason="Patient moved")
    assert Trip.objects.get().status == "cancelled"
    assert Ambulance.objects.get(pk=a.pk).status == "available"


def test_the_suppliers_blood_bank_sees_its_available_ambulances_for_dispatch(s):
    amb(s.supplier, "S1")
    amb(s.supplier, "S2", status="maintenance")
    amb(s.receiver, "R1")
    client = as_user(s.supplier_staff)
    assert client.get("/api/ambulances/").status_code == 403  # no registry access
    res = client.get(f"/api/ambulances/available/?hospital={s.receiver.pk}")  # ignored: own hospital only
    assert [a["identifier"] for a in res.json()] == ["S1"]
