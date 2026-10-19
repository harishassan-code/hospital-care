"""Blood bank rules for Sprint 3: registration, screening, expiry, stock, donors and appointments.
Every change is audit-logged; status changes go through the shared change_status()."""

from collections import Counter
from datetime import datetime, timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.permissions import may_change
from apps.audit.services import record
from apps.resources.services import change_status
from apps.resources.state_machine import TransitionNotAllowed

from .models import (
    REQUIRED_TESTS,
    AppointmentStatus,
    BloodGroup,
    BloodUnit,
    Component,
    DonationAppointment,
    Donor,
    TestResult,
    UnitStatus,
    min_donation_interval,
)
from .serializers import BloodUnitSerializer

# ── Units ─────────────────────────────────────────────────────────────────────────────────────────


def check_donation_interval(donor: Donor, collected_at: datetime) -> None:
    """Story #21: refuse a unit from a donor who gave blood less than the minimum interval ago.
    Units collected the same day are one donation split into components, so they're allowed."""
    day = timezone.localdate(collected_at)
    window_start = collected_at - min_donation_interval()
    clash = (
        donor.units.filter(
            collected_at__gt=window_start, collected_at__lt=collected_at + min_donation_interval()
        )
        .exclude(collected_at__date=day)
        .exists()
    )
    if clash:
        days = min_donation_interval().days
        raise ValidationError(
            {"donorId": [f"This donor gave blood less than {days} days from this collection."]}
        )


def register_unit(serializer, actor) -> BloodUnit:
    """Create a blood unit from a valid serializer, scoped to the actor's hospital, and audit-log it."""
    donor = serializer.validated_data.get("donor")
    if donor is not None:
        check_donation_interval(donor, serializer.validated_data["collected_at"])
    unit = serializer.save(hospital=getattr(actor, "hospital", None))
    after = BloodUnitSerializer(unit, context={"now": timezone.now()}).data
    record(actor, "bloodunit.registered", unit, after=dict(after))
    return unit


def _locked_unit(donation_number: str, actor) -> BloodUnit:
    unit = BloodUnit.objects.select_for_update().get(donation_number=donation_number)
    if not may_change(actor, unit):
        raise PermissionDenied("You can only change blood units in your own hospital.")
    return unit


def missing_tests(unit: BloodUnit) -> list[str]:
    done = set(unit.tests.filter(passed=True).values_list("test", flat=True))
    return [test for test in REQUIRED_TESTS if test not in done]


@transaction.atomic
def record_test(donation_number: str, *, test: str, passed: bool, reason: str, actor) -> BloodUnit:
    """
    Story #18. Record one screening result on a quarantined unit.
    A failed test discards the unit straight away; once every required test has passed it is released.
    """
    unit = _locked_unit(donation_number, actor)
    if unit.status != UnitStatus.QUARANTINED:
        raise TransitionNotAllowed(
            f"Tests can only be recorded on quarantined units; this one is {unit.status}."
        )
    if unit.tests.filter(test=test).exists():
        raise ValidationError({"test": ["This test is already recorded for this unit."]})
    result = TestResult.objects.create(unit=unit, test=test, passed=passed, reason=reason, recorded_by=actor)
    record(actor, "bloodunit.test_recorded", unit, after={"test": test, "passed": passed}, reason=reason)

    if not passed:
        change_status(
            unit, "discard", actor=actor, reason=f"{result.get_test_display()} test failed: {reason}"
        )
    elif not missing_tests(unit):
        change_status(unit, "release", actor=actor, reason="All screening tests passed")
    return unit


@transaction.atomic
def apply_unit_action(donation_number: str, action: str, *, actor, reason: str = "") -> BloodUnit:
    """Move a unit along its lifecycle by hand (reserve, issue, expire…), with the screening rules kept:
    release needs every test passed, and discard needs a reason."""
    unit = _locked_unit(donation_number, actor)
    if action == "release" and missing_tests(unit):
        raise TransitionNotAllowed(
            f"Can't release a unit with tests still missing: {', '.join(missing_tests(unit))}."
        )
    if action == "discard" and not reason.strip():
        raise ValidationError({"reason": ["Say why the unit is being discarded."]})
    return change_status(unit, action, actor=actor, reason=reason)


def expire_overdue_units(now=None) -> int:
    """Story #19: mark every unit past its expiry date as expired (and audit-log each). Returns how many.
    Run by the `expire_blood_units` command (schedule it) and before the stock view, so it's never stale."""
    now = now or timezone.now()
    count = 0
    expirable = [s for (s, action) in BloodUnit.machine.transitions if action == "expire"]
    overdue = BloodUnit.objects.filter(status__in=expirable, expires_at__lte=now).values_list("pk", flat=True)
    for pk in list(overdue):
        with transaction.atomic():
            unit = BloodUnit.objects.select_for_update().get(pk=pk)
            if unit.status in expirable and unit.expires_at <= now:
                change_status(unit, "expire", actor=None, reason="Past its expiry date")
                count += 1
    return count


# ── Stock (story #19) ─────────────────────────────────────────────────────────────────────────────


def stock_summary(units, *, near_expiry_days: int, low_stock_units: int, now=None) -> dict:
    """Counts per blood group and component, with near-expiry units and low-stock flags.
    Only `available` units count as usable stock."""
    now = now or timezone.now()
    soon = now + timedelta(days=near_expiry_days)
    usable = units.filter(status=UnitStatus.AVAILABLE, expires_at__gt=now)
    available = Counter(usable.values_list("group", "component"))
    reserved = Counter(
        units.filter(status=UnitStatus.RESERVED, expires_at__gt=now).values_list("group", "component")
    )
    quarantined = Counter(
        units.filter(status=UnitStatus.QUARANTINED, expires_at__gt=now).values_list("group", "component")
    )
    near = usable.filter(expires_at__lte=soon)
    near_counts = Counter(near.values_list("group", "component"))
    rows = []
    for group in BloodGroup.values:
        for component in Component.values:
            key = (group, component)
            rows.append(
                {
                    "group": group,
                    "component": component,
                    "available": available[key],
                    "reserved": reserved[key],
                    "quarantined": quarantined[key],
                    "nearExpiry": near_counts[key],
                    "low": available[key] < low_stock_units,
                }
            )
    return {
        "nearExpiryDays": near_expiry_days,
        "lowStockUnits": low_stock_units,
        "rows": rows,
        "nearExpiryUnits": BloodUnitSerializer(
            near.order_by("expires_at"), many=True, context={"now": now}
        ).data,
    }


# ── Donors (stories #20, #21) ─────────────────────────────────────────────────────────────────────


def next_donor_code() -> str:
    last = Donor.objects.filter(code__startswith="DNR-").aggregate(m=Max("code"))["m"]
    number = int(last.split("-")[1]) + 1 if last else 1
    return f"DNR-{number:05d}"


@transaction.atomic
def register_donor(serializer, actor) -> Donor:
    donor = serializer.save(code=next_donor_code(), hospital=getattr(actor, "hospital", None))
    record(actor, "donor.registered", donor, after={"code": donor.code, "bloodGroup": donor.blood_group})
    return donor


@transaction.atomic
def screen_donor(donor: Donor, *, eligible: bool, reason: str, deferred_until, actor) -> Donor:
    """Story #21: record the outcome of eligibility screening. Ineligible needs a reason;
    no end date means a permanent deferral."""
    if not may_change(actor, donor):
        raise PermissionDenied("You can only screen donors registered at your own hospital.")
    before = {"deferralReason": donor.deferral_reason, "deferredUntil": str(donor.deferred_until or "")}
    if eligible:
        donor.deferral_reason, donor.deferred_until = "", None
    else:
        if not reason.strip():
            raise ValidationError({"reason": ["Say why the donor is not eligible."]})
        donor.deferral_reason, donor.deferred_until = reason.strip(), deferred_until
    donor.save(update_fields=["deferral_reason", "deferred_until"])
    after = {"deferralReason": donor.deferral_reason, "deferredUntil": str(donor.deferred_until or "")}
    record(actor, "donor.screened", donor, before=before, after=after, reason=reason)
    return donor


# ── Appointments (story #22) ──────────────────────────────────────────────────────────────────────


def book_appointment(donor: Donor, starts_at: datetime, *, actor) -> DonationAppointment:
    slot = settings.BLOOD_APPOINTMENT_SLOT_MINUTES
    local = timezone.localtime(starts_at)
    if local.second or local.microsecond or (local.hour * 60 + local.minute) % slot:
        raise ValidationError(
            {"startsAt": [f"Appointments start on a {slot}-minute slot (e.g. 10:00, 10:{slot:02d})."]}
        )
    if starts_at <= timezone.now():
        raise ValidationError({"startsAt": ["Pick a time in the future."]})
    eligible, why, _ = donor.eligibility(on=local.date())
    if not eligible:
        raise ValidationError({"donorId": [f"This donor can't be booked: {why}"]})
    hospital = getattr(actor, "hospital", None) or donor.hospital
    if donor.appointments.filter(status=AppointmentStatus.BOOKED, starts_at__gte=timezone.now()).exists():
        raise ValidationError({"donorId": ["This donor already has an upcoming appointment."]})
    try:
        with transaction.atomic():
            appointment = DonationAppointment.objects.create(
                donor=donor, hospital=hospital, starts_at=starts_at
            )
    except IntegrityError:
        raise ValidationError({"startsAt": ["That slot is already booked."]}) from None
    record(
        actor,
        "appointment.booked",
        appointment,
        after={"donor": donor.code, "startsAt": starts_at.isoformat()},
    )
    return appointment


@transaction.atomic
def cancel_appointment(appointment: DonationAppointment, *, actor) -> DonationAppointment:
    if not may_change(actor, appointment):
        raise PermissionDenied("You can only cancel appointments at your own hospital.")
    if appointment.status != AppointmentStatus.BOOKED:
        raise TransitionNotAllowed("This appointment is already cancelled.")
    appointment.status = AppointmentStatus.CANCELLED
    appointment.save(update_fields=["status"])
    record(
        actor,
        "appointment.cancelled",
        appointment,
        before={"status": "booked"},
        after={"status": "cancelled"},
    )
    return appointment
