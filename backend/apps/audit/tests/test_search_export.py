"""Story #56: audit search and CSV export."""

import pytest

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.audit.services import record

pytestmark = pytest.mark.django_db


@pytest.fixture
def entries(make_user, make_hospital):
    nurse = make_user(Role.NURSE, email="nurse@example.com")
    hospital = make_hospital()
    record(nurse, "transfer.requested", hospital, reason="For EC-1")
    record(nurse, "transfer.approved", hospital)
    record(None, "bed.status_changed", hospital, reason="cleaning")
    return hospital


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_only_admins_read_the_audit_log(client_as, role):
    assert client_as(role).get("/api/audit/").status_code == 403


def test_filters_by_actor_action_prefix_and_text(client_as, entries):
    admin = client_as(Role.ADMIN)
    assert admin.get("/api/audit/?actor=nurse").json()["count"] == 2
    assert admin.get("/api/audit/?action=transfer.").json()["count"] == 2
    assert admin.get("/api/audit/?action=transfer.approved").json()["count"] == 1
    assert admin.get("/api/audit/?q=EC-1").json()["count"] == 1
    assert admin.get("/api/audit/?from=2000-01-01&to=2000-01-02").json()["count"] == 0
    first = admin.get("/api/audit/").json()["results"][0]
    assert first["action"] == "bed.status_changed" and first["actor"] == "system"


def test_export_streams_csv_and_is_itself_audited(client_as, entries):
    res = client_as(Role.ADMIN).get("/api/audit/export.csv?action=transfer.")
    assert res.status_code == 200 and res["Content-Type"] == "text/csv"
    lines = b"".join(res.streaming_content).decode().strip().splitlines()
    assert lines[0].startswith("at,actor_email,action") and len(lines) == 3
    exported = AuditLog.objects.get(action="audit.exported")
    assert exported.after == {"filters": {"action": "transfer."}}
