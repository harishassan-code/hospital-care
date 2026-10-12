"""Bed lifecycle on the shared resource state machine. Mirrors TRANSITIONS in features/beds/beds.ts."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.accounts.permissions import may_change
from apps.resources.services import change_status

from .models import BED_LIFECYCLE, Bed, BedStatus

ACTIONS = BED_LIFECYCLE.actions


@transaction.atomic
def apply_bed_action(label: str, action: str, *, actor) -> Bed:
    """
    Apply `action` to the bed, locking its row so two nurses can't move the same bed at once.
    Raises PermissionDenied for another hospital's bed, TransitionNotAllowed for a refused move.
    """
    bed = Bed.objects.select_for_update().select_related("ward").get(label=label)
    if not may_change(actor, bed):
        raise PermissionDenied("You can only change beds in your own hospital.")
    if bed.status == BedStatus.OCCUPIED:
        bed.clear_patient()  # discharge is the only way out of occupied; a refused move saves nothing
    return change_status(bed, action, actor=actor)
