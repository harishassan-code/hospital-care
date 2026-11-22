"""B10 (#56): audit CSV export: columns, filters, escaping, the 10,000-row cap, streaming, audit."""

import csv
import io
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit import services
from apps.audit.models import AuditLog
from apps.audit.services import MAX_EXPORT_ROWS, ExportGrewPastCap

from .helpers import stamp

pytestmark = pytest.mark.django_db

URL = "/api/audit/entries/export/"
HEADER = ["at", "actorEmail", "action", "targetType", "targetId", "targetRepr", "reason", "before", "after"]


@pytest.fixture
def admin(client_as):
    return client_as(Role.ADMIN)


def rows_of(response) -> list[list[str]]:
    """The file's rows, parsed. Reads the whole stream, which is what writes the audit record."""
    text = b"".join(response.streaming_content).decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


def test_the_file_is_a_streamed_csv_attachment_named_by_the_export_date(admin):
    response = admin.get(URL)
    assert response.status_code == 200
    assert response.streaming
    assert response["Content-Type"] == "text/csv; charset=utf-8"
    assert (
        response["Content-Disposition"] == f'attachment; filename="audit-{timezone.localdate():%Y-%m-%d}.csv"'
    )


def test_columns_come_in_order_with_utc_times_and_json_cells(admin):
    stamp(
        "2026-11-17T18:59:59+00:00",
        action="hospital.updated",
        target_type="hospitals.hospital",
        target_id="3",
        target_repr="CityCare",
        reason="Renamed",
        before={"name": "Old", "beds": 2},
        after={"name": "New"},
    )
    stamp("2026-11-18T10:00:00+00:00", action="bed.reserved", before=None, after={"status": "reserved"})

    rows = rows_of(admin.get(URL))

    assert rows[0] == HEADER
    assert rows[1] == [
        "2026-11-18T10:00:00Z",
        "admin@example.com",
        "bed.reserved",
        "beds.bed",
        "1",
        "Bed 1",
        "",
        "",
        '{"status": "reserved"}',
    ]
    assert rows[2] == [
        "2026-11-17T18:59:59Z",
        "admin@example.com",
        "hospital.updated",
        "hospitals.hospital",
        "3",
        "CityCare",
        "Renamed",
        '{"beds": 2, "name": "Old"}',
        '{"name": "New"}',
    ]


def test_the_export_takes_the_same_filters_as_the_search(admin):
    stamp(action="bed.reserved", reason="keep me")
    stamp(action="hospital.updated", reason="skip me")
    rows = rows_of(admin.get(URL, {"action": "bed."}))
    assert len(rows) == 2 and rows[1][6] == "keep me"


def test_karachi_days_apply_to_the_export_too(admin):
    stamp("2026-11-17T18:59:59+00:00", reason="17 Nov")
    stamp("2026-11-17T19:00:00+00:00", reason="18 Nov")
    rows = rows_of(admin.get(URL, {"from": "2026-11-18", "to": "2026-11-18"}))
    assert [row[6] for row in rows[1:]] == ["18 Nov"]


def test_cells_a_spreadsheet_would_run_get_a_single_quote(admin):
    stamp(
        "2026-11-18T11:00:00+00:00",
        actor_email="nurse@example.com",
        target_repr="Ward = ICU",
        reason="Ward = ICU",
    )
    stamp(
        "2026-11-18T12:00:00+00:00",
        actor_email="@evil.example",
        action="\tsneak",
        target_type="beds.bed",
        target_id="-5",
        target_repr="+SUM(1)",
        reason='=HYPERLINK("http://x","click")',
        before=-5,
        after={"note": "=1+1"},
    )
    stamp("2026-11-18T13:00:00+00:00", target_repr="\rnewline")

    rows = rows_of(admin.get(URL))  # newest first

    assert rows[1][1] == "admin@example.com"  # the 13:00 row: plain, except its escaped repr
    assert rows[2][1:7] == [
        "'@evil.example",
        "'\tsneak",
        "beds.bed",
        "'-5",
        "'+SUM(1)",
        '\'=HYPERLINK("http://x","click")',
    ]
    assert rows[2][7:] == ["'-5", '{"note": "=1+1"}']
    assert rows[3][6] == "Ward = ICU"  # not at the start, so untouched
    assert rows[1][5] == "'\rnewline"


def test_an_empty_result_is_just_the_header(admin):
    assert rows_of(admin.get(URL, {"action": "nothing."})) == [HEADER]


def test_more_than_the_cap_is_refused_with_400_and_no_file(admin):
    AuditLog.objects.bulk_create(
        [
            AuditLog(
                action="bed.reserved",
                target_type="beds.bed",
                target_id="1",
                target_repr="Bed 1",
                actor_email="a@x",
            )
            for _ in range(MAX_EXPORT_ROWS + 1)
        ]
    )
    response = admin.get(URL)
    assert response.status_code == 400
    assert "10,000" in response.json()["detail"]
    assert not response.has_header("Content-Disposition")
    assert not AuditLog.objects.filter(action="audit.exported").exists()


def test_exactly_the_cap_is_allowed(admin):
    with patch.object(services, "MAX_EXPORT_ROWS", 3):
        for _ in range(3):
            stamp()
        assert len(rows_of(admin.get(URL))) == 4  # header and three rows
        stamp()
        assert admin.get(URL).status_code == 400


def test_rows_that_arrive_after_the_count_stop_the_stream_without_a_record(make_user):
    actor = make_user(Role.ADMIN)
    for _ in range(4):
        stamp()
    with patch.object(services, "MAX_EXPORT_ROWS", 3):
        with pytest.raises(ExportGrewPastCap):
            b"".join(services.export_chunks(AuditLog.objects.all(), actor, services.AuditFilters()))
    assert not AuditLog.objects.filter(action="audit.exported").exists()


def test_a_completed_export_is_audit_logged_with_its_filters_and_row_count(admin):
    stamp(action="bed.reserved")
    stamp(action="bed.discharged")
    stamp(action="hospital.updated")

    rows_of(admin.get(URL, {"action": "bed."}))

    entry = AuditLog.objects.get(action="audit.exported")
    assert entry.actor_email == "admin@example.com"
    assert (entry.target_type, entry.target_repr) == ("accounts.user", "admin@example.com")
    assert entry.target_id == str(entry.actor.pk)
    assert entry.after == {"filters": {"action": "bed."}, "rows": 2}


def test_an_export_nobody_finishes_reading_writes_no_record(admin):
    stamp()
    admin.get(URL)
    assert not AuditLog.objects.filter(action="audit.exported").exists()


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_only_admins_can_export(client_as, role):
    assert client_as(role).get(URL).status_code == 403


def test_signed_out_users_cannot_export(api):
    assert api.get(URL).status_code == 403


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_writes_answer_405(admin, method):
    assert getattr(admin, method)(URL, {}, format="json").status_code == 405
