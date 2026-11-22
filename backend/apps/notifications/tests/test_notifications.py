"""Story #52: notification service."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.matching.tests.reservation_support import staff
from apps.notifications import services
from apps.notifications.models import Notification
from apps.transfers.tests.transfer_support import reach, scenario

pytestmark = pytest.mark.django_db


def as_user(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_a_transfer_request_reaches_the_suppliers_answering_role_as_critical(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    reach(s, "requested")
    note = Notification.objects.get(kind="transfer.requested")
    assert note.hospital == s.supplier and note.severity == "critical"
    blood_bank = as_user(s.supplier_staff).get("/api/notifications/").json()
    assert [n["kind"] for n in blood_bank] == ["transfer.requested"]
    pharmacist = staff(make_user, s.supplier, Role.PHARMACIST)
    assert as_user(pharmacist).get("/api/notifications/").json() == []
    assert as_user(s.requester).get("/api/notifications/?unread=1").json() == []  # other hospital


def test_approval_tells_the_receiver(make_user, make_hospital):
    s = scenario(make_user, make_hospital)
    reach(s, "approved")
    kinds = [n["kind"] for n in as_user(s.requester).get("/api/notifications/").json()]
    assert "transfer.approved" in kinds


def test_read_state_is_per_user_and_acknowledge_clears_the_banner(make_user, make_hospital):
    hospital = make_hospital()
    a, b = staff(make_user, hospital, Role.NURSE), make_user(Role.DOCTOR, email="d2@x.com", hospital=hospital)
    note = services.notify(
        hospital_id=hospital.pk, kind="emergency.escalated", title="Esc", severity="critical"
    )
    ca, cb = as_user(a), as_user(b)
    assert ca.get("/api/notifications/unread-count/").json() == {"unread": 1, "critical": 1}
    assert ca.post(f"/api/notifications/{note.pk}/read/").status_code == 204
    assert ca.get("/api/notifications/unread-count/").json() == {"unread": 0, "critical": 1}
    assert cb.get("/api/notifications/unread-count/").json()["unread"] == 1
    ca.post(f"/api/notifications/{note.pk}/acknowledge/")
    assert ca.get("/api/notifications/?critical=1").json() == []
    assert cb.post("/api/notifications/read-all/").json() == {"marked": 1}


def test_patients_get_nothing_and_strangers_get_404(make_user, make_hospital, client_as):
    hospital = make_hospital()
    note = services.notify(hospital_id=hospital.pk, kind="x.y", title="t")
    assert client_as(Role.PATIENT).get("/api/notifications/").status_code == 403
    other = staff(make_user, make_hospital(name="Other"), Role.NURSE)
    assert as_user(other).post(f"/api/notifications/{note.pk}/read/").status_code == 404


def test_a_failing_channel_never_breaks_the_action(monkeypatch, make_hospital):
    class Broken(services.Channel):
        def send(self, notification):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(services, "CHANNELS", [Broken()])
    assert services.notify(hospital_id=make_hospital().pk, kind="x.y", title="t") is None
    assert not Notification.objects.exists()
