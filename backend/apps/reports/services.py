"""
Operational reports for management (B18, #66): requests, fulfilment time and blood wastage over a date range.
Read-only: nothing here changes data. Every rule for the range, the figures and what counts lives here; the
views only parse and answer, and `exports.py` only lays the same dict out as CSV or PDF (#67).
"""

import datetime as dt
import math
import re
import statistics
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, Min, Sum
from rest_framework.exceptions import APIException

from apps.blood.models import BloodUnit, UnitStatus
from apps.core import clock
from apps.emergencies.models import (
    EmergencyRequest,
    RequestItem,
    RequestStatus,
    RequestStatusChange,
    ResourceType,
    Severity,
)
from apps.hospitals.models import Hospital
from apps.matching.models import Allocation

DEFAULT_DAYS = 30
MAX_DAYS = 366
ZONE = ZoneInfo(settings.TIME_ZONE)
ONE_DAY = dt.timedelta(days=1)
DATE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
ID_SHAPE = re.compile(r"[0-9]{1,9}")
# A unit that left the shelf for a patient, or was thrown away for a failed test, didn't expire unused.
NOT_EXPIRED_UNUSED = (UnitStatus.ISSUED, UnitStatus.DISCARDED)


class ReportQueryError(APIException):
    """A range or filter the reports refuse. Answers 400 with {"detail": message}."""

    status_code = 400


@dataclass(frozen=True)
class ReportRange:
    """Whole days, both ends included, in the server's time zone; optionally one hospital."""

    start: dt.date
    end: dt.date
    hospital: Hospital | None = None

    @property
    def lower(self) -> dt.datetime:
        """The start of the first day, in UTC (times are stored in UTC)."""
        return _midnight_utc(self.start)

    @property
    def upper(self) -> dt.datetime:
        """The start of the day after the last one, in UTC: the range is lower <= t < upper."""
        return _midnight_utc(self.end + ONE_DAY)

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def describe(self) -> dict:
        return {
            "range": {"from": self.start.isoformat(), "to": self.end.isoformat(), "days": self.days},
            "hospital": {"id": self.hospital.pk, "name": self.hospital.name} if self.hospital else None,
        }

    def within(self, field: str) -> dict:
        """Queryset filter keyword arguments for `field` falling inside the range."""
        return {f"{field}__gte": self.lower, f"{field}__lt": self.upper}


def _midnight_utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time.min, tzinfo=ZONE).astimezone(dt.UTC)


def _text(params, key: str) -> str:
    return (params.get(key) or "").strip()


def _day(params, key: str) -> dt.date | None:
    raw = _text(params, key)
    if not raw:
        return None
    if not DATE_SHAPE.fullmatch(raw):
        raise ReportQueryError(f"{key} must be a date as YYYY-MM-DD.")
    try:
        day = dt.date.fromisoformat(raw)
        _midnight_utc(day + ONE_DAY)
    except (ValueError, OverflowError):
        raise ReportQueryError(f"{key} isn't a real date.") from None
    return day


def range_from(params, *, today: dt.date | None = None) -> ReportRange:
    """
    The range asked for. Neither date: the 30 days ending today. Only `from`: up to today. Only `to`: the 30
    days ending then. Refused: a malformed date, `to` before `from`, more than 366 days, an unknown hospital.
    """
    today = today or clock.localdate()
    start, end = _day(params, "from"), _day(params, "to")
    if end is None:
        end = today if start is None or start <= today else start
    if start is None:
        start = end - dt.timedelta(days=DEFAULT_DAYS - 1)
    if end < start:
        raise ReportQueryError("to must be the same day as from, or later.")
    if (end - start).days + 1 > MAX_DAYS:
        raise ReportQueryError(f"A report covers at most {MAX_DAYS} days. Choose a shorter range.")

    hospital = None
    raw = _text(params, "hospital")
    if raw:
        if not ID_SHAPE.fullmatch(raw):
            raise ReportQueryError("hospital must be a hospital id.")
        hospital = Hospital.objects.filter(pk=int(raw)).first()
        if hospital is None:
            raise ReportQueryError("No hospital with that id.")
    return ReportRange(start, end, hospital)


def _counts(rows, key: str, choices) -> list[dict]:
    """One entry per choice, in the choices' order, with 0 for those that didn't occur."""
    found = {row[key]: row["count"] for row in rows}
    return [{"id": value, "label": label, "count": found.get(value, 0)} for value, label in choices]


# ── Requests ─────────────────────────────────────────────────────────────────────────────────────────


def _cases(r: ReportRange):
    cases = EmergencyRequest.objects.filter(**r.within("created_at"))
    return cases.filter(hospital=r.hospital) if r.hospital else cases


def requests_report(r: ReportRange) -> dict:
    """Cases opened in the range (by severity, by current status), what they asked for, and the
    allocations made in the range for cases at the hospital (or anywhere, without a filter)."""
    cases = _cases(r)
    by_severity = cases.values("severity").annotate(count=Count("id")).order_by()
    by_status = cases.values("status").annotate(count=Count("id")).order_by()

    needs = (
        RequestItem.objects.filter(request__in=cases)
        .values("resource_type")
        .annotate(count=Count("id"), units=Sum("quantity"))
        .order_by()
    )
    needs_found = {row["resource_type"]: row for row in needs}

    allocations = Allocation.objects.filter(**r.within("at"))
    if r.hospital:
        allocations = allocations.filter(request__hospital=r.hospital)
    allocated = allocations.values("request_item__resource_type").annotate(count=Count("id")).order_by()
    allocated_found = {row["request_item__resource_type"]: row["count"] for row in allocated}

    by_type = []
    for value, label in ResourceType.choices:
        row = needs_found.get(value) or {}
        by_type.append(
            {
                "id": value,
                "label": label,
                "needs": row.get("count", 0),
                "unitsAsked": row.get("units") or 0,
                "unitsAllocated": allocated_found.get(value, 0),
            }
        )
    return {
        "total": cases.count(),
        "bySeverity": _counts(by_severity, "severity", Severity.choices),
        "byStatus": _counts(by_status, "status", RequestStatus.choices),
        "byResourceType": by_type,
        "allocations": sum(allocated_found.values()),
    }


# ── Fulfilment time ──────────────────────────────────────────────────────────────────────────────────


def percentile(values: list[float], share: float) -> float:
    """Nearest-rank percentile: the smallest value with at least `share` of the values at or below it."""
    ordered = sorted(values)
    return ordered[max(math.ceil(share * len(ordered)), 1) - 1]


def _stats(minutes: list[float]) -> dict:
    if not minutes:
        return {"count": 0, "medianMinutes": None, "averageMinutes": None, "p90Minutes": None}
    return {
        "count": len(minutes),
        "medianMinutes": round(statistics.median(minutes), 1),
        "averageMinutes": round(statistics.fmean(minutes), 1),
        "p90Minutes": round(percentile(minutes, 0.9), 1),
    }


def fulfilment_report(r: ReportRange) -> dict:
    """
    Time from opening a case to the first time it reached fulfilled, for cases whose first fulfilment falls
    in the range (a case reopened and fulfilled again counts once, by the first). Also the cases opened in
    the range that never reached fulfilled, by their current status.
    """
    changes = RequestStatusChange.objects.filter(to_status=RequestStatus.FULFILLED)
    if r.hospital:
        changes = changes.filter(request__hospital=r.hospital)
    firsts = (
        changes.values("request_id", "request__severity", "request__created_at")
        .annotate(first=Min("at"))
        .filter(first__gte=r.lower, first__lt=r.upper)
        .order_by()
    )
    by_severity: dict[str, list[float]] = {value: [] for value in Severity.values}
    every = []
    for row in firsts:
        minutes = max((row["first"] - row["request__created_at"]).total_seconds() / 60, 0.0)
        every.append(minutes)
        by_severity[row["request__severity"]].append(minutes)

    ever_fulfilled = RequestStatusChange.objects.filter(to_status=RequestStatus.FULFILLED).values(
        "request_id"
    )
    never = _cases(r).exclude(pk__in=ever_fulfilled).values("status").annotate(count=Count("id")).order_by()
    return {
        "overall": _stats(every),
        "bySeverity": [
            {"id": value, "label": label, **_stats(by_severity[value])} for value, label in Severity.choices
        ],
        "notFulfilled": [row for row in _counts(never, "status", RequestStatus.choices) if row["count"]],
    }


# ── Blood wastage ────────────────────────────────────────────────────────────────────────────────────


def wastage_report(r: ReportRange, *, now: dt.datetime | None = None) -> dict:
    """
    Blood units wasted in the range, by hospital, group and component:
    - expired: the unit's expiry date fell in the range and has passed, and it was never issued or discarded
      (marked expired, or still on the shelf past expiry because the sweep hasn't run yet);
    - discarded: thrown away (a failed screening test) on a day in the range.
    """
    now = now or clock.now()
    units = BloodUnit.objects.all()
    if r.hospital:
        units = units.filter(hospital=r.hospital)
    expired = (
        units.filter(**r.within("expires_at"), expires_at__lte=now)
        .exclude(status__in=NOT_EXPIRED_UNUSED)
        .values("hospital__name", "group", "component")
        .annotate(count=Count("id"))
        .order_by()
    )
    discarded = (
        units.filter(status=UnitStatus.DISCARDED, **r.within("status_since"))
        .values("hospital__name", "group", "component")
        .annotate(count=Count("id"))
        .order_by()
    )

    rows: dict[tuple, dict] = {}
    for kind, found in (("expired", expired), ("discarded", discarded)):
        for row in found:
            key = (row["hospital__name"] or "", row["group"], row["component"])
            entry = rows.setdefault(
                key,
                {"hospital": key[0], "group": key[1], "component": key[2], "expired": 0, "discarded": 0},
            )
            entry[kind] = row["count"]
    ordered = [rows[key] for key in sorted(rows)]
    return {
        "expired": sum(row["expired"] for row in ordered),
        "discarded": sum(row["discarded"] for row in ordered),
        "rows": ordered,
    }


def build(r: ReportRange) -> dict:
    """All three reports for one range: the JSON the API answers and the data the exports lay out."""
    return {
        **r.describe(),
        "generatedAt": clock.now().isoformat(),
        "requests": requests_report(r),
        "fulfilment": fulfilment_report(r),
        "wastage": wastage_report(r),
    }
