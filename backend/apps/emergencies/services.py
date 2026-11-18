"""Emergency case rules (stories #30, #32, #34, #35). Changes are audit-logged; moves are in the timeline."""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone

from apps.accounts.permissions import may_change
from apps.audit.services import record

from .models import (
    REQUEST_LIFECYCLE,
    EmergencyRequest,
    RequestItem,
    RequestStatus,
    RequestStatusChange,
    ResourceType,
    Severity,
)

REFERENCE_ATTEMPTS = 5
# The statuses an escalation can start from (see REQUEST_LIFECYCLE).
ACTIVE = (RequestStatus.OPEN, RequestStatus.MATCHING, RequestStatus.PARTIALLY_FULFILLED)


class OutcomeNoteRequired(Exception):
    """Closing a case needs an outcome note. Views answer 400, and nothing changes."""

    def __init__(self):
        super().__init__("Add an outcome note to close the case.")


def next_reference(year: int) -> str:
    """`EC-<year>-<sequence>`, one higher than the year's last case. Numbers grow past 4 digits if needed."""
    prefix = f"EC-{year}-"
    numbers = [
        int(ref.removeprefix(prefix))
        for ref in EmergencyRequest.objects.filter(reference__startswith=prefix).values_list(
            "reference", flat=True
        )
    ]
    return f"{prefix}{max(numbers, default=0) + 1:04d}"


def _need_fields(item: dict) -> dict:
    """The stored fields of one validated need: its own type's field only, the others stay blank."""
    kind = item["type"]
    if kind == ResourceType.BLOOD:
        return {"resource_type": kind, "blood_group": item["group"], "component": item["component"]}
    if kind == ResourceType.BED:
        return {"resource_type": kind, "bed_type": item["bedType"]}
    if kind == ResourceType.EQUIPMENT:
        return {"resource_type": kind, "equipment_type": item["equipmentType"]}
    return {"resource_type": kind, "capability": item["capability"]}


@transaction.atomic
def create_case(*, severity: str, patient_ref: str, items: list[dict], actor) -> EmergencyRequest:
    """
    Open a case with its needs at the actor's hospital and audit-log it. Two cases created at the same moment
    can pick the same reference; the unique constraint refuses the second, which retries with the next one
    (each attempt is a savepoint, so a refused one leaves nothing behind).
    """
    for attempt in range(REFERENCE_ATTEMPTS):
        try:
            with transaction.atomic():
                case = EmergencyRequest.objects.create(
                    reference=next_reference(timezone.localdate().year),
                    hospital=getattr(actor, "hospital", None),
                    created_by=actor,
                    severity=severity,
                    patient_ref=patient_ref.strip(),
                )
                break
        except IntegrityError:
            if attempt == REFERENCE_ATTEMPTS - 1:
                raise
    RequestStatusChange.objects.create(
        request=case, from_status="", to_status=case.status, action="create", actor=actor
    )
    RequestItem.objects.bulk_create(
        RequestItem(request=case, quantity=item["quantity"], **_need_fields(item)) for item in items
    )
    record(
        actor,
        "emergencyrequest.created",
        case,
        after={"severity": severity, "status": case.status, "items": len(items)},
    )
    return case


def move_case(case: EmergencyRequest, action: str, *, note: str, actor, at=None) -> EmergencyRequest:
    """
    The one place a status changes: the move, its timeline entry and its audit record. Raises
    TransitionNotAllowed and saves nothing if the lifecycle refuses the move. The caller holds the row lock
    and the transaction. `actor` None is the system (automatic escalation).
    """
    at = at or timezone.now()
    before = case.status
    case.status = REQUEST_LIFECYCLE.next(before, action)
    case.save(update_fields=["status"])
    RequestStatusChange.objects.create(
        request=case, from_status=before, to_status=case.status, action=action, note=note, actor=actor, at=at
    )
    record(
        actor,
        "emergencyrequest.status_changed",
        case,
        before={"status": before},
        after={"status": case.status},
        reason=note or action,
    )
    return case


@transaction.atomic
def apply_case_action(reference: str, action: str, *, note: str, actor) -> EmergencyRequest:
    """
    Move a case along its lifecycle, with its timeline entry and an audit record, in one transaction. The row
    is locked, so two people can't move the same case at once. Another hospital's case is a 404, as if it
    didn't exist. Closing needs an outcome note (story #35): OutcomeNoteRequired, nothing saved. Raises
    TransitionNotAllowed and saves nothing if the move isn't allowed from the status.
    """
    case = EmergencyRequest.objects.select_for_update().filter(reference=reference).first()
    if case is None or not may_change(actor, case):
        raise Http404("No emergency case with that id.")
    # A move the lifecycle refuses is reported first, even when the note is missing too.
    REQUEST_LIFECYCLE.next(case.status, action)
    if action == "close" and not note.strip():
        raise OutcomeNoteRequired()
    moved = move_case(case, action, note=note, actor=actor)
    if action in ("close", "cancel"):
        # Story #48: a finished case releases the stock its unfinished transfers pinned at other hospitals.
        from apps.transfers.services import cancel_for_case  # transfers builds on emergencies

        cancel_for_case(moved, actor=actor, reason=f"Case {moved.reference} {moved.status}")
    return moved


def _overdue_ids(cutoff):
    """Critical active cases whose latest timeline entry (entry into the status) is before `cutoff`."""
    return (
        EmergencyRequest.objects.filter(severity=Severity.CRITICAL, status__in=ACTIVE)
        .annotate(entered=Max("history__at"))
        .filter(entered__lt=cutoff)
        .values_list("pk", flat=True)
    )


def escalate_overdue(now=None) -> int:
    """
    Escalate each critical case that has sat in its current status for EMERGENCY_ESCALATION_MINUTES
    (story #35). It runs as the system (no actor), through the same move as a person's, so the timeline says
    why. Returns how many it escalated. Idempotent: an escalated case is no longer active.

    ponytail: a request-time sweep (the case list and detail GETs call this). Ceiling: read traffic or case
    volume grows; then run `escalate_overdue_cases` on a scheduler and drop the calls from the views.
    """
    now = now or timezone.now()
    minutes = settings.EMERGENCY_ESCALATION_MINUTES
    cutoff = now - timedelta(minutes=minutes)
    candidates = list(_overdue_ids(cutoff))
    if not candidates:
        return 0
    escalated = 0
    with transaction.atomic():
        # skip_locked: a case another run or a person is moving right now is left for them, not waited on.
        locked = EmergencyRequest.objects.select_for_update(skip_locked=True).filter(
            pk__in=candidates, severity=Severity.CRITICAL, status__in=ACTIVE
        )
        for case in locked:
            # Re-check under the lock: a case resumed since the query has a fresh window and stays.
            if case.history.aggregate(last=Max("at"))["last"] >= cutoff:
                continue
            move_case(
                case,
                "escalate",
                note=f"Not fulfilled within {minutes} minutes (automatic)",
                actor=None,
                at=now,
            )
            escalated += 1
    return escalated
