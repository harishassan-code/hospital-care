from django.http import HttpResponse
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import module_permission
from apps.audit.services import record
from apps.emergencies.services import escalate_overdue

from . import exports, services

FORMATS = {
    "csv": ("text/csv; charset=utf-8", exports.to_csv),
    "pdf": ("application/pdf", exports.to_pdf),
}


class FirstRenderer(DefaultContentNegotiation):
    """The export's `?format=csv|pdf` names the file to build. DRF would read `format` as a renderer to pick
    (URL_FORMAT_OVERRIDE) and answer 404 for csv and pdf, so this view answers its errors as JSON always."""

    def select_renderer(self, request, renderers, format_suffix=None):
        return renderers[0], renderers[0].media_type


class ReportReadView(APIView):
    """Read only, admins (the `reports` module). The overdue-case sweep runs first, as the command centre's
    does, so case statuses in the report agree with the case pages."""

    http_method_names = ["get", "head", "options"]

    def initial(self, request, *args, **kwargs):
        # Writes answer 405 for everyone, before the role check, as the audit trail's do.
        if request.method.lower() not in self.http_method_names:
            raise MethodNotAllowed(request.method)
        super().initial(request, *args, **kwargs)


class ReportView(ReportReadView):
    """GET /api/reports/?from=&to=&hospital= → {range, hospital, generatedAt, requests, fulfilment,
    wastage}."""

    permission_classes = [module_permission("reports")]

    def get(self, request):
        report_range = services.range_from(request.query_params)
        escalate_overdue()
        return Response(services.build(report_range))


class ReportExportView(ReportReadView):
    """
    GET /api/reports/export/?format=csv|pdf&from=&to=&hospital= → the same report as a file,
    reports-<from>-to-<to>.<format>. Each export is audit-logged as report.exported.
    """

    permission_classes = [module_permission("reports")]
    content_negotiation_class = FirstRenderer

    def get(self, request):
        kind = (request.query_params.get("format") or "").strip().lower()
        if kind not in FORMATS:
            raise services.ReportQueryError("format must be csv or pdf.")
        report_range = services.range_from(request.query_params)
        escalate_overdue()
        report = services.build(report_range)
        content_type, render = FORMATS[kind]
        response = HttpResponse(render(report), content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{exports.filename(report, kind)}"'
        record(
            request.user,
            "report.exported",
            request.user,
            after={**report_range.describe(), "format": kind},
        )
        return response
