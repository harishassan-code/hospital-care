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
