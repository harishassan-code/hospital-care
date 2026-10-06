"""Bed lifecycle. Mirrors TRANSITIONS in frontend/src/features/beds/beds.ts."""

from django.db import transaction
from django.utils import timezone

from .models import Bed, BedStatus

S = BedStatus

# (current status, action) -> next status. Anything not listed is refused.
TRANSITIONS: dict[tuple[str, str], str] = {
    (S.OCCUPIED, "discharge"): S.CLEANING,
    (S.CLEANING, "markReady"): S.FREE,
    (S.FREE, "reserve"): S.RESERVED,
    (S.FREE, "outOfService"): S.OUT_OF_SERVICE,
    (S.RESERVED, "cancelReservation"): S.FREE,
    (S.OUT_OF_SERVICE, "returnToService"): S.CLEANING,
}

ACTIONS = sorted({action for _, action in TRANSITIONS})


class BedActionRefused(Exception):
    pass


@transaction.atomic
def apply_bed_action(label: str, action: str) -> Bed:
    """Apply `action` to the bed, locking its row so two nurses can't move the same bed at once."""
    bed = Bed.objects.select_for_update().select_related("ward").get(label=label)
    next_status = TRANSITIONS.get((bed.status, action))
    if next_status is None:
        raise BedActionRefused(f"Can't {action} a bed that is {bed.get_status_display().lower()}.")
    if bed.status == S.OCCUPIED:
        bed.clear_patient()
    bed.status = next_status
    bed.status_since = timezone.now()
    bed.save()
    return bed
