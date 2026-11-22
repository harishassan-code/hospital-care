"""Specialist rules (B16, stories #61 and #62): profiles, on-call windows, the overlap rule and
"available now".

Every write runs in one transaction. It locks the specialist (and the window, when there is one), checks
the role and the hospital, checks the rule, writes the change and writes one audit record. A rule that
breaks raises a DRF ValidationError (400, keyed by the field it names), PermissionDenied (403) or
SpecialistConflict (409). The views only translate those into status codes."""

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.permissions import can_edit, may_change
from apps.audit.services import record
from apps.hospitals.models import Hospital

from .models import OnCallWindow, Specialist

MODULE = "specialists"
DUPLICATE_NAME = "A specialist with this name is already listed at this hospital."
ENDED = "This window has already ended. Add a window that is still to come, or one that is on now."
STARTED = "This window has started, so it stays as history."

# The profile fields the API accepts, mapped to the model's attribute names.
FIELDS = {"name": "name", "specialty": "specialty", "isActive": "is_active"}


class SpecialistConflict(Exception):
    """The change isn't allowed now because the window has started. Views answer 409, and nothing changes."""


def _check_write(actor, specialist: Specialist) -> None:
    """Writes need edit on specialists, and a non-admin may change only their own hospital's specialists."""
    if not can_edit(actor.effective_role, MODULE):
        raise PermissionDenied("Your role can't change specialists.")
    if not may_change(actor, specialist):
        raise PermissionDenied("You can only change specialists at your own hospital.")


def window_covering(specialist: Specialist, now) -> OnCallWindow | None:
    """The window covering `now` (start inclusive, end exclusive), from the windows `with_schedule` loaded."""
    return next((w for w in specialist.upcoming_windows if w.starts_at <= now < w.ends_at), None)


def _overlapping_window(specialist: Specialist, starts_at, ends_at) -> OnCallWindow | None:
    """A window of this specialist that shares any time with [starts_at, ends_at). Back-to-back windows don't
    clash."""
    return (
        specialist.on_call_windows.filter(starts_at__lt=ends_at, ends_at__gt=starts_at)
        .order_by("starts_at")
        .first()
    )


def _clash_message(window: OnCallWindow) -> str:
    start, end = timezone.localtime(window.starts_at), timezone.localtime(window.ends_at)
    return f"Overlaps an on-call window from {start:%d %b %H:%M} to {end:%d %b %H:%M}."


def _window_times(window: OnCallWindow) -> dict:
    return {
        "startsAt": timezone.localtime(window.starts_at).isoformat(),
        "endsAt": timezone.localtime(window.ends_at).isoformat(),
    }


@transaction.atomic
def create_specialist(hospital: Hospital, *, name: str, specialty: str, actor) -> Specialist:
    """List a specialist at `hospital`. A name is unique per hospital, in any case."""
    _check_write(actor, Specialist(hospital=hospital))
    if Specialist.objects.filter(hospital=hospital, name__iexact=name).exists():
        raise ValidationError({"name": [DUPLICATE_NAME]})
    try:
        with transaction.atomic():
            specialist = Specialist.objects.create(hospital=hospital, name=name, specialty=specialty)
    except IntegrityError:  # someone listed the same name at the same moment
        raise ValidationError({"name": [DUPLICATE_NAME]}) from None
    record(
        actor,
        "specialist.created",
        specialist,
        after={"name": specialist.name, "specialty": specialist.specialty, "hospital": hospital.name},
    )
    return specialist


@transaction.atomic
def update_specialist(specialist_id: int, changes: dict, *, actor) -> Specialist:
    """Change a profile's name, specialty or whether it is active. Only the fields that really change are
    saved and audited, and an unchanged update writes nothing. Another hospital's profile is 403 for a
    non-admin."""
    specialist = get_object_or_404(Specialist.objects.select_for_update(), pk=specialist_id)
    _check_write(actor, specialist)
    before, after = {}, {}
    for key, value in changes.items():
        current = getattr(specialist, FIELDS[key])
        if current != value:
            before[key], after[key] = current, value
    if not after:
        return specialist
    if "name" in after and (
        Specialist.objects.filter(hospital_id=specialist.hospital_id, name__iexact=after["name"])
        .exclude(pk=specialist.pk)
        .exists()
    ):
        raise ValidationError({"name": [DUPLICATE_NAME]})
    for key, value in after.items():
        setattr(specialist, FIELDS[key], value)
    specialist.save(update_fields=[FIELDS[key] for key in after])
    record(actor, "specialist.updated", specialist, before=before, after=after)
    return specialist


@transaction.atomic
def add_on_call_window(specialist_id: int, *, starts_at, ends_at, actor, now) -> OnCallWindow:
    """Add an on-call window. It must end after it starts, must not have ended by `now`, and must not overlap
    another window of the same specialist. The specialist's row lock makes the overlap check hold under
    concurrent writes."""
    specialist = get_object_or_404(Specialist.objects.select_for_update(), pk=specialist_id)
    _check_write(actor, specialist)
    if ends_at <= starts_at:
        raise ValidationError({"endsAt": ["The window must end after it starts."]})
    if ends_at <= now:
        raise ValidationError({"endsAt": [ENDED]})
    if clash := _overlapping_window(specialist, starts_at, ends_at):
        raise ValidationError({"startsAt": [_clash_message(clash)]})
    window = OnCallWindow.objects.create(specialist=specialist, starts_at=starts_at, ends_at=ends_at)
    record(actor, "on_call.created", window, after=_window_times(window))
    return window


@transaction.atomic
def remove_on_call_window(specialist_id: int, window_id: int, *, actor, now) -> None:
    """Remove a window that hasn't started. A window that has started stays as history (409). A window that
    isn't this specialist's is a 404, so the URL can't reach another specialist's rota."""
    specialist = get_object_or_404(Specialist.objects.select_for_update(), pk=specialist_id)
    _check_write(actor, specialist)
    window = get_object_or_404(OnCallWindow.objects.select_for_update(), pk=window_id, specialist=specialist)
    if window.starts_at <= now:
        raise SpecialistConflict(STARTED)
    record(actor, "on_call.deleted", window, before=_window_times(window))
    window.delete()
