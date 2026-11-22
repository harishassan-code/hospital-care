"""
The one call other modules use to log a critical action (story 8.1), and the read side of the trail:
search and CSV export (B10, #56). Every rule for filters, paging and export lives here.
"""

import csv
import datetime as dt
import itertools
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q, QuerySet
from rest_framework.exceptions import APIException

from .models import AuditLog
from .serializers import AuditEntrySerializer

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
# Export holds at most this many rows. Above it the export is refused, never cut short (spec, question 2).
MAX_EXPORT_ROWS = 10_000
EXPORT_CHUNK = 500
EXPORT_COLUMNS = [
    "at",
    "actorEmail",
    "action",
    "targetType",
    "targetId",
    "targetRepr",
    "reason",
    "before",
    "after",
]
# What a spreadsheet would run as a formula (OWASP's list), plus tab and carriage return.
FORMULA_STARTS = ("=", "+", "-", "@", "\t", "\r")
ZONE = ZoneInfo(settings.TIME_ZONE)
ONE_DAY = dt.timedelta(days=1)
DATE_SHAPE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# Nine digits at most keeps OFFSET inside every database's integer range.
WHOLE_SHAPE = re.compile(r"[0-9]{1,9}")


class AuditQueryError(APIException):
    """A filter, paging value or export the API refuses. Answers 400 with {"detail": message}."""

    status_code = 400


class ExportGrewPastCap(RuntimeError):
    """More rows matched while the file was written. The response breaks off, so no complete file is sent."""


def record(actor, action: str, target, *, before=None, after=None, reason: str = "") -> AuditLog:
    """
    Log `action` on `target` (any model instance) by `actor` (a user, or None for the system).
    `before`/`after` are JSON-able dicts of the values that changed.
    """
    signed_in = actor is not None and actor.is_authenticated
    return AuditLog.objects.create(
        actor=actor if signed_in else None,
        actor_email=actor.email if signed_in else "",
        action=action,
        target_type=target._meta.label_lower,
        target_id=str(target.pk),
        target_repr=str(target)[:200],
        before=before,
        after=after,
        reason=reason[:300],
    )


@dataclass(frozen=True)
class AuditFilters:
    """The search filters after parsing. A blank or missing filter is "" or None."""

    actor: str = ""
    action: str = ""
    target_type: str = ""
    target_id: str = ""
    start: dt.date | None = None
    end: dt.date | None = None
    text: str = ""

    def set_filters(self) -> dict[str, str]:
        """The filters that are set, as the export records them in the audit entry."""
        values = {
            "actor": self.actor,
            "action": self.action,
            "targetType": self.target_type,
            "targetId": self.target_id,
            "from": self.start.isoformat() if self.start else "",
            "to": self.end.isoformat() if self.end else "",
            "q": self.text,
        }
        return {key: value for key, value in values.items() if value}


@dataclass(frozen=True)
class AuditPage:
    count: int
    limit: int
    offset: int
    rows: QuerySet


def _text(params, key: str) -> str:
    return (params.get(key) or "").strip()


def _midnight_utc(day: dt.date) -> dt.datetime:
    """The start of a Karachi calendar day (TIME_ZONE), in UTC, because times are stored in UTC."""
    return dt.datetime.combine(day, dt.time.min, tzinfo=ZONE).astimezone(dt.timezone.utc)


def _day(params, key: str) -> dt.date | None:
    raw = _text(params, key)
    if not raw:
        return None
    if not DATE_SHAPE.fullmatch(raw):
        raise AuditQueryError(f"{key} must be a date as YYYY-MM-DD.")
    try:
        day = dt.date.fromisoformat(raw)
        _midnight_utc(day)
        _midnight_utc(day + ONE_DAY)  # the day after, for the upper bound of "to"
    except (ValueError, OverflowError):
        raise AuditQueryError(f"{key} isn't a date the audit trail can search.") from None
    return day


def _whole(params, key: str, default: int) -> int:
    raw = _text(params, key)
    if not raw:
        return default
    if not WHOLE_SHAPE.fullmatch(raw):
        raise AuditQueryError(f"{key} must be a whole number, 0 or more.")
    return int(raw)


def filters_from(params) -> AuditFilters:
    filters = AuditFilters(
        actor=_text(params, "actor"),
        action=_text(params, "action"),
        target_type=_text(params, "targetType"),
        target_id=_text(params, "targetId"),
        start=_day(params, "from"),
        end=_day(params, "to"),
        text=_text(params, "q"),
    )
    if filters.start and filters.end and filters.end < filters.start:
        raise AuditQueryError("to must be the same day as from, or later.")
    return filters


def paging_from(params) -> tuple[int, int]:
    """(limit, offset). A limit above the maximum is cut to the maximum."""
    return min(_whole(params, "limit", DEFAULT_LIMIT), MAX_LIMIT), _whole(params, "offset", 0)


def apply_filters(queryset: QuerySet, filters: AuditFilters) -> QuerySet:
    """All filters combine with AND. Newest first, ties broken by id."""
    if filters.actor:
        queryset = queryset.filter(actor_email__iexact=filters.actor)
    if filters.action:
        queryset = queryset.filter(action__startswith=filters.action)
    if filters.target_type:
        queryset = queryset.filter(target_type=filters.target_type)
    if filters.target_id:
        queryset = queryset.filter(target_id=filters.target_id)
    if filters.start:
        queryset = queryset.filter(at__gte=_midnight_utc(filters.start))
    if filters.end:
        queryset = queryset.filter(at__lt=_midnight_utc(filters.end + ONE_DAY))
    if filters.text:
        queryset = queryset.filter(
            Q(actor_email__icontains=filters.text)
            | Q(action__icontains=filters.text)
            | Q(target_repr__icontains=filters.text)
            | Q(target_id__icontains=filters.text)
            | Q(reason__icontains=filters.text)
        )
    return queryset.order_by("-at", "-id")


def search(params) -> AuditPage:
    """One page of matching entries: one count query and one select."""
    queryset = apply_filters(AuditLog.objects.all(), filters_from(params))
    limit, offset = paging_from(params)
    return AuditPage(
        count=queryset.count(),
        limit=limit,
        offset=offset,
        rows=queryset[offset : offset + limit],
    )


def export_query(params) -> tuple[AuditFilters, QuerySet]:
    """The filtered entries for a CSV. Refused with 400 when there are more than MAX_EXPORT_ROWS."""
    filters = filters_from(params)
    queryset = apply_filters(AuditLog.objects.all(), filters)
    if queryset.count() > MAX_EXPORT_ROWS:
        raise AuditQueryError(
            f"More than {MAX_EXPORT_ROWS:,} entries match, so the file would be incomplete. "
            "Narrow the filters, for example a shorter date range, and export again."
        )
    return filters, queryset


class _Echo:
    """A file-like object that returns what is written, so csv.writer can build the text chunk by chunk."""

    def write(self, value: str) -> str:
        return value


def _csv_row(entry: dict) -> list[str]:
    cells = []
    for column in EXPORT_COLUMNS:
        value = entry[column]
        if column in ("before", "after"):
            text = "" if value is None else json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = value or ""
        cells.append("'" + text if text.startswith(FORMULA_STARTS) else text)
    return cells


def export_chunks(queryset: QuerySet, actor, filters: AuditFilters) -> Iterator[str]:
    """
    The CSV, one chunk at a time as rows are read. The audit record comes after the last row, so an export
    cut short writes none. If rows arrive after the count, the stream stops with ExportGrewPastCap.
    """
    writer = csv.writer(_Echo())
    yield writer.writerow(EXPORT_COLUMNS)
    rows = 0
    entries = queryset[: MAX_EXPORT_ROWS + 1].iterator(chunk_size=EXPORT_CHUNK)
    for batch in itertools.batched(entries, EXPORT_CHUNK):
        rows += len(batch)
        if rows > MAX_EXPORT_ROWS:
            raise ExportGrewPastCap(f"Audit export passed {MAX_EXPORT_ROWS} rows while it was being written.")
        cells = AuditEntrySerializer(batch, many=True).data
        yield "".join(writer.writerow(_csv_row(entry)) for entry in cells)
    record(actor, "audit.exported", actor, after={"filters": filters.set_filters(), "rows": rows})
