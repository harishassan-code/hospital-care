"""Story #51: Ambulance dispatch and trip tracking."""

import pytest
from django.urls import reverse

from apps.accounts.models import Role
from apps.ambulances.models import Ambulance, AmbulanceStatus, TripStatus
from apps.ambulances.services import TripConflict, advance_trip, dispatch_for_transfer
from apps.transfers.models import TransferStatus
from apps.transfers.tests.transfer_support import reach, scenario

pytestmark = pytest.mark.django_db


def test_dispatch_requires_available_ambulance(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "approved")
    busy = Ambulance.objects.create(
        identifier="AMB-BUSY", ambulance_type="basic", hospital=s.supplier, status=AmbulanceStatus.IN_USE
    )
    with pytest.raises(TripConflict, match="available"):
        dispatch_for_transfer(transfer, ambulance_id=busy.pk, actor=s.supplier_staff)


def test_trip_lifecycle_moves_transfer(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "approved")
    amb = Ambulance.objects.create(identifier="AMB-1", ambulance_type="basic", hospital=s.supplier)
    trip = dispatch_for_transfer(transfer, ambulance_id=amb.pk, actor=s.supplier_staff)
    assert trip.status == TripStatus.DISPATCHED
    transfer.refresh_from_db()
    assert transfer.status == TransferStatus.DISPATCHED
    amb.refresh_from_db()
    assert amb.status == AmbulanceStatus.IN_USE

    trip = advance_trip(trip.pk, "startRoute", actor=s.supplier_staff)
    assert trip.status == TripStatus.EN_ROUTE

    trip = advance_trip(trip.pk, "arrive", actor=s.supplier_staff)
    assert trip.status == TripStatus.ARRIVED
    transfer.refresh_from_db()
    assert transfer.status == TransferStatus.IN_TRANSIT

    trip = advance_trip(trip.pk, "complete", actor=s.supplier_staff)
    assert trip.status == TripStatus.COMPLETED
    amb.refresh_from_db()
    assert amb.status == AmbulanceStatus.AVAILABLE


def test_trip_api(client_as, make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    transfer = reach(s, "approved")
    amb = Ambulance.objects.create(identifier="AMB-2", ambulance_type="transport", hospital=s.supplier)
    supplier = client_as(Role.BLOOD_BANK, hospital=s.supplier, email="bb-sup@demo.test")
    res = supplier.post(reverse("transfer-trip", args=[transfer.pk]), {"ambulanceId": amb.pk}, format="json")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "dispatched"
    assert body["trip"]["status"] == "dispatched"
    assert body["trip"]["ambulance"]["identifier"] == "AMB-2"

    trip_id = body["trip"]["id"]
    res = supplier.post(reverse("trip-action", args=[trip_id]), {"action": "startRoute"}, format="json")
    assert res.status_code == 200
    assert res.json()["trip"]["status"] == "enRoute"