"""
Unit tests for the backend (Sprint 1), one per business rule.

Each test checks a single function or method on its own, not through the API.
Run with:  docker compose exec backend pytest tests/test_backend_units.py -v
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import Role
from apps.accounts.permissions import can_edit, can_see
from apps.accounts.services import split_full_name
from apps.blood.models import BloodUnit, UnitStatus
from apps.hospitals.models import Bed, BedStatus, Ward
from apps.hospitals.services import apply_bed_action
from apps.resources.state_machine import TransitionNotAllowed


def test_split_full_name_into_first_and_last_name():
    """UT-01: sign-up's full name is split into first name and the rest as last name."""
    assert split_full_name("Sara Ali Khan") == ("Sara", "Ali Khan")
    assert split_full_name("  Hassan  ") == ("Hassan", "")
    assert split_full_name("") == ("", "")


def test_role_permissions_match_the_frontend_role_table():
    """UT-02: each role can only see and edit the modules it is allowed to."""
    # A nurse can edit beds and view pharmacy, but can't see the blood bank.
    assert can_edit(Role.NURSE, "beds")
    assert can_see(Role.NURSE, "pharmacy") and not can_edit(Role.NURSE, "pharmacy")
    assert not can_see(Role.NURSE, "blood")
    # A doctor can view everything but edit nothing.
    assert can_see(Role.DOCTOR, "beds") and not can_edit(Role.DOCTOR, "beds")
    # A patient has no staff access at all.
    assert not can_see(Role.PATIENT, "beds")


def test_blood_unit_past_expiry_counts_as_expired_unless_issued():
    """UT-03: a unit past its expiry date is reported as expired, even if its stored status says available."""
    now = timezone.now()
    unit = BloodUnit(
        donation_number="G7731 26 000001",
        group="O-",
        component="redCells",
        collected_at=now - timedelta(days=43),
        expires_at=now - timedelta(days=1),
        status=UnitStatus.AVAILABLE,
        location="Blood fridge 1",
    )
    assert unit.effective_status(now) == UnitStatus.EXPIRED

    unit.status = UnitStatus.ISSUED  # already given to a patient, so it stays "issued"
    assert unit.effective_status(now) == UnitStatus.ISSUED

    unit.expires_at = now + timedelta(days=5)  # not expired yet
    unit.status = UnitStatus.AVAILABLE
    assert unit.effective_status(now) == UnitStatus.AVAILABLE


@pytest.mark.django_db
def test_bed_discharge_clears_patient_and_illegal_moves_are_refused(make_user):
    """UT-04: discharging a bed sends it to cleaning and removes the patient; a wrong move is refused."""
    ward = Ward.objects.create(code="icu", name="ICU", kind="Intensive care")
    Bed.objects.create(
        ward=ward,
        label="ICU-01",
        status=BedStatus.OCCUPIED,
        patient_initials="A.B.",
        patient_age=40,
        patient_sex="F",
        admitted_at=timezone.now(),
    )

    nurse = make_user(Role.NURSE)
    bed = apply_bed_action("ICU-01", "discharge", actor=nurse)
    assert bed.status == BedStatus.CLEANING
    assert bed.patient_initials == "" and bed.patient_age is None and bed.admitted_at is None

    # A bed that is being cleaned can't be reserved; it must be marked ready first.
    with pytest.raises(TransitionNotAllowed):
        apply_bed_action("ICU-01", "reserve", actor=nurse)
    bed.refresh_from_db()
    assert bed.status == BedStatus.CLEANING
