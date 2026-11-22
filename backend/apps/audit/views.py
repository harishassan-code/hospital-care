from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission

from . import services
from .serializers import AuditEntrySerializer


class AuditReadView(APIView):
    """Read only: every other method answers 405, whoever asks. Reads need the audit view (admins only)."""

    http_method_names = ["get", "head", "options"]

    def initial(self, request, *args, **kwargs):
        if request.method.lower() not in self.http_method_names:
            raise MethodNotAllowed(request.method)
        super().initial(request, *args, **kwargs)


class AuditEntryListView(AuditReadView):
    """
    GET /api/audit/entries/?actor=&action=&targetType=&targetId=&from=&to=&q=&limit=&offset=
    → {count, limit, offset, results}, newest first. Rules in services.py.
    """

    permission_classes = [module_permission("audit")]

    def get(self, request):
        page = services.search(request.query_params)
        return Response(
            {
                "count": page.count,
                "limit": page.limit,
                "offset": page.offset,
                "results": AuditEntrySerializer(page.rows, many=True).data,
            }
        )


class AuditExportView(AuditReadView):
    """
    GET /api/audit/entries/export/ with the same filters → a CSV attachment, audit-<date>.csv.
    Over 10,000 rows: 400 and no file.
    """

    permission_classes = [module_permission("audit")]

    def get(self, request):
        filters, queryset = services.export_query(request.query_params)
        response = StreamingHttpResponse(
            services.export_chunks(queryset, request.user, filters),
            content_type="text/csv; charset=utf-8",
        )
        response["Content-Disposition"] = f'attachment; filename="audit-{timezone.localdate():%Y-%m-%d}.csv"'
        return response
