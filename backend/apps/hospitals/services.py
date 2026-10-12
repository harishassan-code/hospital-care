"""Bed lifecycle on the shared resource state machine. Mirrors TRANSITIONS in features/beds/beds.ts."""

from django.db import transaction

from apps.resources.services import change_status

from .models import BED_LIFECYCLE, Bed, BedStatus

ACTIONS = BED_LIFECYCLE.actions


@transaction.atomic
def apply_bed_action(label: str, action: str, *, actor) -> Bed:
    """Apply `action` to the bed, locking its row so two nurses can't move the same bed at once."""
    bed = Bed.objects.select_for_update().select_related("ward").get(label=label)
    if bed.status == BedStatus.OCCUPIED:
        bed.clear_patient()  # discharge is the only way out of occupied; a refused move saves nothing
    return change_status(bed, action, actor=actor)
