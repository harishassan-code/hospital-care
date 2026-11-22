"""B18 (#66, #67): the reports API and its CSV and PDF export: access, answers, files and the audit record."""

import csv
import io

import pytest

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.matching.tests.reservation_support import blood_need

from .support import fulfilled, opened

pytestmark = pytest.mark.django_db

URL = "/api/reports/"
EXPORT = "/api/reports/export/"
NOVEMBER = {"from": "2026-11-01", "to": "2026-11-10"}


@pytest.fixture
def admin(client_as):
    return client_as(Role.ADMIN)


@pytest.fixture
def one_fulfilled_case(make_hospital):
    hospital = make_hospital()
    case = opened(hospital, "2026-11-02T10:00:00+05:00", blood_need("O-", quantity=2), severity="critical")
    fulfilled(case, "2026-11-02T10:45:00+05:00")
    return hospital


@pytest.mark.parametrize("role", [r for r in Role if r != Role.ADMIN])
@pytest.mark.parametrize("url", [URL, EXPORT + "?format=csv"])
def test_only_admins_can_read_or_export_reports(client_as, role, url):
    assert client_as(role).get(url).status_code == 403


def test_signed_out_callers_are_refused(api):
    assert api.get(URL).status_code == 403
    assert api.get(EXPORT, {"format": "pdf"}).status_code == 403


def test_reports_cannot_be_written(admin):
    assert admin.post(URL, {}, format="json").status_code == 405
    assert admin.delete(EXPORT).status_code == 405


def test_the_report_answers_json_for_the_range(admin, one_fulfilled_case):
    response = admin.get(URL, NOVEMBER)
    assert response.status_code == 200
    body = response.json()
    assert body["range"] == {"from": "2026-11-01", "to": "2026-11-10", "days": 10}
    assert body["hospital"] is None
    assert body["requests"]["total"] == 1
    assert body["fulfilment"]["overall"]["medianMinutes"] == 45.0
    assert body["wastage"] == {"expired": 0, "discarded": 0, "rows": []}


def test_the_hospital_filter_narrows_the_report(admin, one_fulfilled_case, make_hospital):
    other = make_hospital("Seaview Hospital")
    body = admin.get(URL, {**NOVEMBER, "hospital": other.pk}).json()
    assert body["hospital"] == {"id": other.pk, "name": "Seaview Hospital"}
    assert body["requests"]["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-11-10", "to": "2026-11-01"},
        {"from": "2025-01-01", "to": "2026-11-10"},
        {"hospital": "x"},
    ],
)
def test_a_bad_range_is_400_with_a_message(admin, params):
    response = admin.get(URL, params)
    assert response.status_code == 400
    assert response.json()["detail"]


def test_csv_export_is_an_attachment_with_every_section_and_is_audit_logged(admin, one_fulfilled_case):
    response = admin.get(EXPORT, {**NOVEMBER, "format": "csv"})

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert response["Content-Disposition"] == 'attachment; filename="reports-2026-11-01-to-2026-11-10.csv"'
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[0] == ["CityCare operational reports"]
    assert rows[1] == ["Period", "2026-11-01 to 2026-11-10 (10 days)"]
    for title in (
        "Requests: 1 case(s) opened, 0 resource(s) allocated",
        "Requests by current status",
        "Requests by resource type",
        "Fulfilment time (opened to fulfilled)",
        "Opened in the range and not fulfilled",
        "Blood wastage: 0 expired unused, 0 discarded",
    ):
        assert [title] in rows
    assert ["All", "1", "45", "45", "45"] in rows

    entry = AuditLog.objects.get(action="report.exported")
    assert entry.after == {
        "range": {"from": "2026-11-01", "to": "2026-11-10", "days": 10},
        "hospital": None,
        "format": "csv",
    }


def test_csv_cells_that_look_like_formulas_are_escaped(admin, make_hospital):
    hospital = make_hospital("=HYPERLINK(1)")
    response = admin.get(EXPORT, {**NOVEMBER, "format": "csv", "hospital": hospital.pk})
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8"))))
    assert rows[2] == ["Hospital", "'=HYPERLINK(1)"]


def test_pdf_export_is_a_pdf_attachment_and_is_audit_logged(admin, one_fulfilled_case):
    response = admin.get(EXPORT, {**NOVEMBER, "format": "pdf", "hospital": one_fulfilled_case.pk})

    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'attachment; filename="reports-2026-11-01-to-2026-11-10.pdf"'
    assert response.content.startswith(b"%PDF-")
    entry = AuditLog.objects.get(action="report.exported")
    assert entry.after["format"] == "pdf"
    assert entry.after["hospital"]["id"] == one_fulfilled_case.pk


def test_a_pdf_with_text_the_core_fonts_cannot_draw_still_exports(admin, make_hospital):
    hospital = make_hospital("اسپتال Hospital")
    response = admin.get(EXPORT, {**NOVEMBER, "format": "pdf", "hospital": hospital.pk})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


@pytest.mark.parametrize("kind", ["", "xlsx"])
def test_an_unknown_format_is_400_and_logs_nothing(admin, kind):
    response = admin.get(EXPORT, {**NOVEMBER, "format": kind})
    assert response.status_code == 400
    assert not AuditLog.objects.filter(action="report.exported").exists()
