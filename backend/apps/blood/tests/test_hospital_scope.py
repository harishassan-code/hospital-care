"""B13 F3: a record at another hospital answers 404, the same reply as an id that doesn't exist, so the
response doesn't show that the record is there. These views look the record up before the service runs.
The service keeps its own 403 as a second guard, but the view no longer reaches it for another hospital."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import (
    AppointmentStatus,
    BloodUnit,
    DonationAppointment,
    Donor,
    TestResult,
    UnitStatus,
)

pytestmark = pytest.mark.django_db

THERE_CODE = "DNR-00009"
THERE_UNIT = "U-THERE"


def make_unit(number, hospital, status=UnitStatus.QUARANTINED):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=number,
        group="O-",
        component="redCells",
        collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=30),
        status=status,
        location="Blood fridge 1",
        hospital=hospital,
    )


@pytest.fixture
def hospitals(make_hospital):
    return make_hospital("Here Hospital"), make_hospital("There Hospital")


@pytest.fixture
def staff(client_as, hospitals):
    """Blood bank staff at the first hospital."""
    return client_as(Role.BLOOD_BANK, hospital=hospitals[0])


@pytest.fixture
def there(hospitals):
    """A donor, an upcoming appointment and a quarantined unit, all registered at the second hospital."""
    _, other = hospitals
    donor = Donor.objects.create(code=THERE_CODE, full_name="Asha Other", blood_group="O-", hospital=other)
    appointment = DonationAppointment.objects.create(
        donor=donor, hospital=other, starts_at=timezone.now() + timedelta(days=2)
    )
    make_unit(THERE_UNIT, other)
    return donor, appointment


def post(client, name, args, body):
    return client.post(reverse(name, args=args), body, format="json")


def test_screening_another_hospitals_donor_is_a_404_and_changes_nothing(staff, there):
    body = {"eligible": False, "reason": "Low haemoglobin"}
    other = post(staff, "blood-donor-screening", [THERE_CODE], body)
    unknown = post(staff, "blood-donor-screening", ["DNR-99999"], body)
    assert other.status_code == 404
    assert (other.status_code, other.json()) == (unknown.status_code, unknown.json())
    assert Donor.objects.get(code=THERE_CODE).deferral_reason == ""
    assert not AuditLog.objects.filter(action="donor.screened").exists()


def test_cancelling_another_hospitals_appointment_is_a_404_and_changes_nothing(staff, there):
    _, appointment = there
    other = post(staff, "blood-appointment-cancel", [appointment.pk], {})
    unknown = post(staff, "blood-appointment-cancel", [999_999], {})
    assert other.status_code == 404
    assert (other.status_code, other.json()) == (unknown.status_code, unknown.json())
    appointment.refresh_from_db()
    assert appointment.status == AppointmentStatus.BOOKED


def test_recording_a_test_on_another_hospitals_unit_is_a_404_and_saves_nothing(staff, there):
    body = {"test": "hiv", "passed": True}
    other = post(staff, "blood-unit-tests", [THERE_UNIT], body)
    unknown = post(staff, "blood-unit-tests", ["NO-SUCH-UNIT"], body)
    assert other.status_code == 404
    assert (other.status_code, other.json()) == (unknown.status_code, unknown.json())
    assert not TestResult.objects.exists()


def test_acting_on_another_hospitals_unit_is_a_404_and_changes_nothing(staff, there):
    body = {"action": "discard", "reason": "Not wanted"}
    other = post(staff, "blood-unit-action", [THERE_UNIT], body)
    unknown = post(staff, "blood-unit-action", ["NO-SUCH-UNIT"], body)
    assert other.status_code == 404
    assert (other.status_code, other.json()) == (unknown.status_code, unknown.json())
    assert BloodUnit.objects.get(donation_number=THERE_UNIT).status == UnitStatus.QUARANTINED


def test_staff_still_act_on_their_own_hospitals_records(client_as, hospitals):
    here, _ = hospitals
    staff = client_as(Role.BLOOD_BANK, hospital=here)
    donor = Donor.objects.create(code="DNR-00001", full_name="Own Donor", blood_group="A+", hospital=here)
    appointment = DonationAppointment.objects.create(
        donor=donor, hospital=here, starts_at=timezone.now() + timedelta(days=2)
    )
    make_unit("U-HERE", here)
    assert post(staff, "blood-appointment-cancel", [appointment.pk], {}).status_code == 200
    assert post(staff, "blood-unit-tests", ["U-HERE"], {"test": "hiv", "passed": True}).status_code == 201
    assert post(staff, "blood-donor-screening", ["DNR-00001"], {"eligible": True}).status_code == 200
