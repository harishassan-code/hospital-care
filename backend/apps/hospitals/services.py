"""Hospital network rules: bed lifecycle, hospital registration and structure, each audit-logged."""

from django.db import transaction
from django.utils.text import slugify
from rest_framework.exceptions import PermissionDenied

from apps.accounts.permissions import may_change
from apps.audit.services import record
from apps.core import clock
from apps.resources.services import change_status

from .models import BED_LIFECYCLE, Bed, BedStatus, Hospital, Ward

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
    if action == "admit":
        bed.admitted_at = clock.now()  # no patient is recorded here; the bed is only marked occupied
    return change_status(bed, action, actor=actor)


@transaction.atomic
def place_patient(
    bed: Bed, *, initials: str, age: int, sex: str, actor, expected_discharge=None, isolation=""
):
    """Put a patient in a free bed (B21): reserve it, then admit, as staff would at the bed board, with the
    patient's initials, age and sex. Raises TransitionNotAllowed and saves nothing if the bed isn't free or is
    held for a case."""
    bed = Bed.objects.select_for_update().select_related("ward").get(pk=bed.pk)
    change_status(bed, "reserve", actor=actor, reason="Patient arriving")
    bed.patient_initials, bed.patient_age, bed.patient_sex = initials, age, sex
    bed.admitted_at, bed.expected_discharge, bed.isolation = clock.now(), expected_discharge, isolation
    return change_status(bed, "admit", actor=actor)


@transaction.atomic
def vacate_bed(bed: Bed, *, actor, reason: str = "discharge") -> Bed:
    """The patient left (B21): the bed goes to cleaning and its patient details are cleared."""
    bed = Bed.objects.select_for_update().select_related("ward").get(pk=bed.pk)
    if bed.status == BedStatus.OCCUPIED:
        bed.clear_patient()
    return change_status(bed, "discharge", actor=actor, reason=reason)


@transaction.atomic
def save_hospital(serializer, actor) -> Hospital:
    """Create or update a hospital from a valid serializer, logging what changed."""
    before = dict(type(serializer)(serializer.instance).data) if serializer.instance else None
    hospital = serializer.save()
    after = dict(type(serializer)(hospital).data)
    if before is None:
        record(actor, "hospital.created", hospital, after=after)
    else:
        changed = [key for key in after if after[key] != before[key]]
        if changed:
            record(
                actor,
                "hospital.updated",
                hospital,
                before={k: before[k] for k in changed},
                after={k: after[k] for k in changed},
            )
    return hospital


def new_ward_code(hospital: Hospital, name: str) -> str:
    """The bed board's ward id: "h<hospital>-<name>", made unique. Never changes afterwards."""
    base = f"h{hospital.pk}-{slugify(name)[:20] or 'ward'}"
    code, n = base, 2
    while Ward.objects.filter(code=code).exists():
        code, n = f"{base}-{n}", n + 1
    return code


def _noun(item) -> str:
    """Audit name of a structure item: department, ward or location."""
    return {"storagelocation": "location"}.get(item._meta.model_name, item._meta.model_name)


@transaction.atomic
def add_structure_item(serializer, hospital: Hospital, actor):
    item = serializer.save(hospital=hospital)
    record(actor, f"{_noun(item)}.created", item, after=dict(serializer.data))
    return item


@transaction.atomic
def remove_structure_item(item, actor) -> None:
    """Raises ProtectedError (409) if something still uses the item."""
    snapshot = {"name": item.name, "hospital": item.hospital_id}
    record(actor, f"{_noun(item)}.deleted", item, before=snapshot)
    item.delete()
