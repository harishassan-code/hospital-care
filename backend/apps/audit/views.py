"""Audit search and CSV export for administrators (story #56). Read-only: AuditLog refuses changes."""

import csv
import json
from datetime import datetime, time

from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission

from .models import AuditLog
from .services import record

PAGE_SIZE = 50
COLUMNS = [
    "at",
    "actor_email",
    "action",
    "target_type",
    "target_id",
    "target_repr",
    "reason",
    "before",
    "after",
]
FILTERS = ("actor", "action", "targetType", "targetId", "from", "to", "q")


def _day(value: str, end: bool):
    try:
        day = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None
    return timezone.make_aware(datetime.combine(day, time.max if end else time.min))


def filtered(params):
    rows = AuditLog.objects.all()
    if actor := params.get("actor", "").strip():
        rows = rows.filter(actor_email__icontains=actor)
    if action := params.get("action", "").strip():
        rows = rows.filter(action__startswith=action) if action.endswith(".") else rows.filter(action=action)
    if target_type := params.get("targetType", "").strip():
        rows = rows.filter(target_type=target_type)
    if target_id := params.get("targetId", "").strip():
        rows = rows.filter(target_id=target_id)
    if start := _day(params.get("from", ""), end=False):
        rows = rows.filter(at__gte=start)
    if stop := _day(params.get("to", ""), end=True):
        rows = rows.filter(at__lte=stop)
    if q := params.get("q", "").strip():
        rows = rows.filter(Q(target_repr__icontains=q) | Q(reason__icontains=q))
    return rows


def row_data(row: AuditLog) -> dict:
    return {
        "id": row.pk,
        "at": row.at.isoformat(),
        "actor": row.actor_email or "system",
        "action": row.action,
        "targetType": row.target_type,
        "targetId": row.target_id,
        "target": row.target_repr,
        "reason": row.reason,
        "before": row.before,
        "after": row.after,
    }


class AuditListView(APIView):
    """GET /api/audit/?actor=&action=transfer.&targetType=&targetId=&from=2026-11-01&to=&q=&page=1 →
    {"count", "page", "pageSize", "results"} newest first (audit: view, admin only)."""

    permission_classes = [module_permission("audit")]

    def get(self, request):
        rows = filtered(request.query_params)
        page = (
            max(int(request.query_params["page"]), 1) if request.query_params.get("page", "").isdigit() else 1
        )
        start = (page - 1) * PAGE_SIZE
        return Response(
            {
                "count": rows.count(),
                "page": page,
                "pageSize": PAGE_SIZE,
                "results": [row_data(r) for r in rows[start : start + PAGE_SIZE]],
            }
        )


class _Echo:
    def write(self, value):
        return value


def _cell(value):
    return json.dumps(value) if isinstance(value, (dict, list)) else value


class AuditExportView(APIView):
    """GET /api/audit/export.csv?<same filters> → streamed CSV. The export itself is audit-logged."""

    permission_classes = [module_permission("audit")]

    def get(self, request):
        params = {k: request.query_params[k] for k in FILTERS if request.query_params.get(k)}
        rows = filtered(request.query_params)
        exported = record(request.user, "audit.exported", request.user, after={"filters": params})
        rows = rows.exclude(pk=exported.pk)
        writer = csv.writer(_Echo())

        def lines():
            yield writer.writerow(COLUMNS)
            for row in rows.iterator(chunk_size=1000):
                yield writer.writerow([_cell(getattr(row, c)) for c in COLUMNS])

        response = StreamingHttpResponse(lines(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="audit-log.csv"'
        return response
