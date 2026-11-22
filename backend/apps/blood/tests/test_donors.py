"""Stories #20 (donor registration), #21 (eligibility screening) and #22 (donation appointments)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import BloodUnit, DonationAppointment, Donor

pytestmark = pytest.mark.django_db

NEW_DONOR = {"fullName": "Test Donor (demo)", "bloodGroup": "O-", "phone": "0300 1234567"}


@pytest.fixture
def staff(client_as):
    return client_as(Role.BLOOD_BANK)


def donor(code="DNR-00001", group="O-", **extra):
    return Donor.objects.create(code=code, full_name="Demo Donor", blood_group=group, **extra)


def give(d, days_ago, number):
    when = timezone.now() - timedelta(days=days_ago)
    return BloodUnit.objects.create(
        donation_number=number, group=d.blood_group, component="redCells", collected_at=when,
        expires_at=when + timedelta(days=42), location="Blood fridge 1", donor=d,
    )  # fmt: skip


def register_unit(client, number, donor_id, days_ago=0, group="O-"):
    collected = (timezone.now() - timedelta(days=days_ago)).isoformat()
    body = {"id": number, "group": group, "component": "plasma", "collectedAt": collected,
            "location": "Plasma freezer A", "donorId": donor_id}  # fmt: skip
    return client.post(reverse("blood-units"), body, format="json")


def next_slot(days=2, hour=10, minute=0):
    day = timezone.localtime() + timedelta(days=days)
    return day.replace(hour=hour, minute=minute, second=0, microsecond=0)


def book(client, donor_id, starts_at):
    return client.post(
        reverse("blood-appointments"), {"donorId": donor_id, "startsAt": starts_at.isoformat()}, format="json"
    )


# ── #20 Donor registration ──────────────────────────────────────────────────────────────────────


def test_register_donor_gets_a_code_and_is_audit_logged(staff):
    res = staff.post(reverse("blood-donors"), NEW_DONOR, format="json")
    assert res.status_code == 201
    data = res.json()
    assert data["id"] == "DNR-00001" and data["bloodGroup"] == "O-" and data["eligible"] is True
    assert staff.post(reverse("blood-donors"), NEW_DONOR, format="json").json()["id"] == "DNR-00002"
    assert AuditLog.objects.filter(action="donor.registered").count() == 2


def test_donor_registration_validates_group_and_phone(staff):
    assert (
        staff.post(reverse("blood-donors"), {**NEW_DONOR, "bloodGroup": "Z+"}, format="json").status_code
        == 400
    )
    assert (
        staff.post(reverse("blood-donors"), {**NEW_DONOR, "phone": "call me"}, format="json").status_code
        == 400
    )


def test_unit_can_be_linked_to_a_donor_and_shows_on_their_record(staff):
    donor()
    assert register_unit(staff, "U1", "DNR-00001").status_code == 201
    assert staff.get(reverse("blood-unit", args=["U1"])).json()["donorId"] == "DNR-00001"
    record = staff.get(reverse("blood-donor", args=["DNR-00001"])).json()
    assert [u["id"] for u in record["units"]] == ["U1"] and record["lastDonationAt"] is not None


def test_unit_group_must_match_the_donor(staff):
    donor(group="A+")
    res = register_unit(staff, "U1", "DNR-00001", group="O-")
    assert res.status_code == 400 and "donorId" in res.json()


def test_search_donors_by_name_code_or_group(staff):
    donor("DNR-00001", group="O-")
    donor("DNR-00002", group="B+")
    assert len(staff.get(reverse("blood-donors"), {"q": "dnr-00002"}).json()) == 1
    assert [d["id"] for d in staff.get(reverse("blood-donors"), {"bloodGroup": "O-"}).json()] == ["DNR-00001"]


# ── #21 Eligibility screening ───────────────────────────────────────────────────────────────────


def test_minimum_interval_between_donations_is_enforced(staff):
    d = donor()
    give(d, days_ago=20, number="OLD")
    res = register_unit(staff, "U2", "DNR-00001")
    assert res.status_code == 400 and "donorId" in res.json()
    record = staff.get(reverse("blood-donor", args=["DNR-00001"])).json()
    assert record["eligible"] is False and "next eligible" in record["ineligibleReason"]


def test_components_from_the_same_donation_day_are_allowed(staff):
    d = donor()
    give(d, days_ago=0, number="RBC")
    assert register_unit(staff, "PLASMA", "DNR-00001").status_code == 201


def test_donor_is_eligible_again_after_the_interval(staff):
    d = donor()
    give(d, days_ago=60, number="OLD")
    assert staff.get(reverse("blood-donor", args=["DNR-00001"])).json()["eligible"] is True


def test_screening_flags_an_ineligible_donor_with_a_reason(staff):
    donor()
    url = reverse("blood-donor-screening", args=["DNR-00001"])
    assert staff.post(url, {"eligible": False}, format="json").status_code == 400  # reason required
    until = (timezone.localdate() + timedelta(days=30)).isoformat()
    data = staff.post(
        url, {"eligible": False, "reason": "Low haemoglobin", "deferredUntil": until}, format="json"
    )
    assert data.json()["eligible"] is False and data.json()["ineligibleReason"] == "Low haemoglobin"
    assert data.json()["eligibleFrom"] == until
    cleared = staff.post(url, {"eligible": True}, format="json").json()
    assert cleared["eligible"] is True and cleared["ineligibleReason"] == ""
    assert AuditLog.objects.filter(action="donor.screened").count() == 2


def test_deferral_without_an_end_date_is_permanent(staff):
    donor(deferral_reason="Positive HCV history")
    assert staff.get(reverse("blood-donor", args=["DNR-00001"])).json()["eligibleFrom"] is None
    assert staff.get(reverse("blood-donor", args=["DNR-00001"])).json()["eligible"] is False


# ── #22 Donation appointments ───────────────────────────────────────────────────────────────────


def test_book_an_eligible_donor_and_list_upcoming(staff):
    donor()
    res = book(staff, "DNR-00001", next_slot())
    assert res.status_code == 201 and res.json()["status"] == "booked"
    assert [a["donorId"] for a in staff.get(reverse("blood-appointments")).json()] == ["DNR-00001"]


def test_slot_cannot_be_double_booked(staff):
    donor("DNR-00001")
    donor("DNR-00002")
    slot = next_slot()
    assert book(staff, "DNR-00001", slot).status_code == 201
    res = book(staff, "DNR-00002", slot)
    assert res.status_code == 400 and "startsAt" in res.json()
    assert DonationAppointment.objects.count() == 1


def test_cancelled_slot_can_be_booked_again(staff):
    donor("DNR-00001")
    donor("DNR-00002")
    slot = next_slot()
    appointment_id = book(staff, "DNR-00001", slot).json()["id"]
    assert (
        staff.post(reverse("blood-appointment-cancel", args=[appointment_id])).json()["status"] == "cancelled"
    )
    assert book(staff, "DNR-00002", slot).status_code == 201
    assert staff.post(reverse("blood-appointment-cancel", args=[appointment_id])).status_code == 409


def test_only_eligible_donors_can_be_booked(staff):
    donor(deferral_reason="Recent tattoo", deferred_until=timezone.localdate() + timedelta(days=90))
    res = book(staff, "DNR-00001", next_slot())
    assert res.status_code == 400 and "Recent tattoo" in res.json()["donorId"][0]


def test_appointments_must_be_on_a_slot_in_the_future(staff):
    donor()
    assert book(staff, "DNR-00001", next_slot(minute=10)).status_code == 400
    assert book(staff, "DNR-00001", next_slot(days=-2)).status_code == 400


def test_donor_cannot_hold_two_upcoming_appointments(staff):
    donor()
    assert book(staff, "DNR-00001", next_slot()).status_code == 201
    assert book(staff, "DNR-00001", next_slot(days=3)).status_code == 400


def test_unit_collected_in_the_future_is_refused(staff):
    res = register_unit(staff, "U1", None, days_ago=-2)
    assert res.status_code == 400 and "collectedAt" in res.json()
