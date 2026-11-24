"""An emergency department's patients (B21): arrival, treatment and leaving, each a small transaction that
moves the visit along VISIT_LIFECYCLE and the bed along its own, and is audit-logged. Written for the
simulation on staging; staff screens read them (B22)."""

import random
from datetime import datetime, timedelta

from django.db import transaction

from apps.audit.services import record
from apps.core import clock
from apps.hospitals.models import Bed
from apps.hospitals.services import place_patient, vacate_bed
from apps.resources.services import held_ids

from .models import ErVisit, VisitOutcome, VisitStatus

TAG_LETTERS = "ABCDEFGHJKLMNPRSTUVWXYZ"
AGE_RANGE = {"0-4": (0, 4), "5-17": (5, 17), "18-39": (18, 39), "40-64": (40, 64), "65+": (65, 94)}
# Visit verbs in the audit log: "ervisit.<verb>".
VERB = {
    "startTreatment": "treatment_started",
    "leaveUnseen": "left_unseen",
    "discharge": "discharged",
    "transfer": "transferred",
    "admit": "admitted",
    "board": "boarding",
}
OUTCOME = {
    "discharge": VisitOutcome.DISCHARGED,
    "transfer": VisitOutcome.TRANSFERRED,
    "admit": VisitOutcome.ADMITTED,
    "leaveUnseen": VisitOutcome.LEFT_UNSEEN,
}


def initials(rand: random.Random) -> str:
    return f"{rand.choice(TAG_LETTERS)}.{rand.choice(TAG_LETTERS)}."


def age_in(band: str, rand: random.Random) -> int:
    lo, hi = AGE_RANGE[band]
    return rand.randint(lo, hi)


@transaction.atomic
def arrive(*, hospital, triage: int, age_band: str, sex: str, complaint: str, actor, rand: random.Random):
    """A patient arrives and joins the queue."""
    visit = ErVisit.objects.create(
        hospital=hospital,
        tag=f"ED-{rand.randint(1000, 9999)}{rand.choice(TAG_LETTERS)}",
        triage=triage,
        age_band=age_band,
        sex=sex,
        complaint=complaint,
        arrived_at=clock.now(),
    )
    record(actor, "ervisit.arrived", visit, after={"triage": triage, "complaint": complaint})
    return visit


def _move(visit: ErVisit, action: str, *, actor, at: datetime, reason: str = "") -> ErVisit:
    before = visit.status
    visit.status = ErVisit.machine.next(before, action)
    if action in OUTCOME:
        visit.outcome = OUTCOME[action]
    if visit.status == VisitStatus.LEFT:
        visit.left_at, visit.due_at = at, None
    visit.save()
    record(
        actor,
        f"ervisit.{VERB[action]}",
        visit,
        before={"status": before},
        after={"status": visit.status, **({"outcome": visit.outcome} if visit.outcome else {})},
        reason=reason,
    )
    return visit


def _locked(visit: ErVisit) -> ErVisit:
    return ErVisit.objects.select_for_update().get(pk=visit.pk)


@transaction.atomic
def start_treatment(visit: ErVisit, *, bed: Bed | None, minutes: float, actor, rand: random.Random):
    """A clinician sees the patient, in `bed` (or a chair, for minor complaints) for about `minutes`."""
    visit = _locked(visit)
    at = clock.now()
    ErVisit.machine.next(visit.status, "startTreatment")  # refuse before touching the bed
    if bed is not None:
        place_patient(
            bed, initials=initials(rand), age=age_in(visit.age_band, rand), sex=visit.sex, actor=actor
        )
        visit.bed = bed
    visit.seen_at, visit.due_at = at, at + timedelta(minutes=minutes)
    return _move(visit, "startTreatment", actor=actor, at=at)


@transaction.atomic
def finish(
    visit: ErVisit,
    action: str,
    *,
    actor,
    ward_bed: Bed | None = None,
    rand: random.Random | None = None,
    age: int | None = None,
    stay_days: int = 0,
    reason: str = "",
):
    """The visit ends: discharged, transferred, admitted (to `ward_bed`), or left unseen. An admission with no
    ward bed free waits in the department (`board`), keeping its emergency bed. The emergency bed goes to
    cleaning when the patient leaves it."""
    visit = _locked(visit)
    at = clock.now()
    ErVisit.machine.next(visit.status, action)
    if action == "admit" and ward_bed is not None:
        rand = rand or random.Random()
        bed = visit.bed
        place_patient(
            ward_bed,
            initials=(bed.patient_initials if bed and bed.patient_initials else initials(rand)),
            age=age if age is not None else age_in(visit.age_band, rand),
            sex=visit.sex,
            actor=actor,
            expected_discharge=clock.localdate() + timedelta(days=stay_days),
            isolation="droplet"
            if visit.complaint == "respiratory" and ward_bed.bed_type == "isolation"
            else "",
        )
        visit.ward_bed = ward_bed
    if action != "board" and visit.bed_id is not None:
        vacate_bed(visit.bed, actor=actor, reason=f"Emergency patient {VERB[action].replace('_', ' ')}")
    return _move(visit, action, actor=actor, at=at, reason=reason)


# ── From the queue page (B22) ─────────────────────────────────────────────────────────────────────

STAFF_ACTIONS = ["startTreatment", "discharge", "admit", "transfer", "leaveUnseen"]
TYPICAL_MINUTES = {1: 220, 2: 180, 3: 135, 4: 80, 5: 40}  # the middle of the simulation's ranges
CHILD_WORDS = ("child", "paediatric", "pediatric", "neonatal")
FEMALE_WORDS = ("obstetric", "postnatal", "labour", "gynaecology", "maternity")


class NoBedFree(Exception):
    """The action needs a bed and none is free. Views answer 409."""


def actions_for(visit: ErVisit) -> list[str]:
    """What staff can do next with this patient. Admitting someone with no ward bed free keeps them waiting
    here ("boarding"), so admit is offered while being treated and while boarding."""
    return {
        VisitStatus.WAITING: ["startTreatment", "leaveUnseen"],
        VisitStatus.TREATING: ["discharge", "admit", "transfer"],
        VisitStatus.BOARDING: ["admit"],
    }.get(visit.status, [])


def _free_emergency_bed(visit: ErVisit, held: set[int]):
    return (
        Bed.objects.filter(hospital=visit.hospital, bed_type="emergency", status="free")
        .exclude(pk__in=held)
        .order_by("label")
        .first()
    )


def _ward_bed(visit: ErVisit, held: set[int]):
    """A free ward bed that suits the patient: intensive care first for triage 1; a children's ward for
    children and not otherwise; an obstetric ward only for women of child-bearing age."""
    child = visit.age_band in ("0-4", "5-17")
    wanted = ["icu", "general"] if visit.triage == 1 else ["general", "isolation"]
    beds = (
        Bed.objects.filter(hospital=visit.hospital, status="free", bed_type__in=wanted)
        .exclude(pk__in=held)
        .select_related("ward")
        .order_by("ward__sort_order", "label")
    )
    for bed_type in wanted:
        for bed in beds:
            if bed.bed_type != bed_type:
                continue
            kind = f"{bed.ward.kind} {bed.ward.name}".lower()
            if any(w in kind for w in CHILD_WORDS) != child:
                continue
            if any(w in kind for w in FEMALE_WORDS) and not (
                visit.sex == "F" and visit.age_band in ("18-39", "40-64")
            ):
                continue
            return bed
    return None


@transaction.atomic
def staff_action(visit: ErVisit, action: str, *, actor) -> ErVisit:
    """A person moves a patient on from the queue page: start treatment (in a free emergency bed, or a chair
    for a minor complaint), discharge, admit (to a suitable free ward bed, or the patient waits in the
    department), transfer, or record that they left unseen. The simulation then leaves this patient to
    staff."""
    visit = _locked(visit)
    ErVisit.machine.next(
        visit.status, "board" if action == "admit" and visit.status == "treating" else action
    )
    held = held_ids(Bed)
    rand = random.Random()
    if action == "startTreatment":
        bed = _free_emergency_bed(visit, held)
        if bed is None and visit.triage <= 3:
            raise NoBedFree("No emergency bed is free. Discharge or move a patient first.")
        visit = start_treatment(visit, bed=bed, minutes=TYPICAL_MINUTES[visit.triage], actor=actor, rand=rand)
    elif action == "admit":
        ward_bed = _ward_bed(visit, held)
        if ward_bed is None:
            if visit.status == VisitStatus.BOARDING:
                raise NoBedFree("No suitable ward bed is free yet; the patient keeps waiting here.")
            visit = finish(visit, "board", actor=actor, reason="No ward bed free")
        else:
            visit = finish(visit, "admit", actor=actor, ward_bed=ward_bed, rand=rand, stay_days=3)
    else:
        visit = finish(visit, action, actor=actor)
    ErVisit.objects.filter(pk=visit.pk).update(handled_by=actor)
    visit.handled_by = actor
    return visit
