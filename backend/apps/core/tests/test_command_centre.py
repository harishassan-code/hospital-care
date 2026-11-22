"""Story #55: city command centre."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accounts.models import Role
from apps.matching.tests.reservation_support import bed, blood_need, case, equipment, unit

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("role", [Role.DOCTOR, Role.NURSE, Role.BLOOD_BANK, Role.PHARMACIST, Role.PATIENT])
def test_only_admins_see_the_command_centre(client_as, role):
    assert client_as(role).get("/api/command-centre/").status_code == 403


def test_aggregates_every_hospital_and_flags_shortages(client_as, make_hospital):
    general, seaview = make_hospital(name="General"), make_hospital(name="Seaview")
    bed(general, "icu", status="occupied")
    bed(seaview, "icu")
    bed(seaview, "general")
    unit(seaview, "O-", expires_in_days=1)
    equipment(general)
    case(general, blood_need("O-"), severity="critical")

    data = client_as(Role.ADMIN).get("/api/command-centre/").json()
    rows = {r["name"]: r for r in data["hospitals"]}
    assert rows["Seaview"]["icu"] == {"free": 1, "total": 1}
    assert rows["Seaview"]["beds"] == {"free": 2, "total": 2}
    assert rows["Seaview"]["redCells"]["O-"] == 1 and rows["Seaview"]["nearExpiry"] == 1
    assert rows["General"]["equipment"] == {"available": 1, "total": 1}
    assert rows["General"]["emergencies"] == {"critical": 1}
    assert data["totals"]["freeIcu"] == 1 and data["totals"]["activeEmergencies"] == 1
    assert {"hospital": "General", "kind": "icu", "level": "critical"} in data["shortages"]
    assert any(s["hospital"] == "Seaview" and s.get("group") == "O-" for s in data["shortages"])


def test_query_count_does_not_grow_with_hospitals(client_as, make_hospital):
    admin = client_as(Role.ADMIN)

    def queries():
        with CaptureQueriesContext(connection) as ctx:
            admin.get("/api/command-centre/")
        return len(ctx)

    make_hospital(name="A")
    few = queries()
    for n in range(5):
        h = make_hospital(name=f"H{n}")
        bed(h)
        unit(h)
    assert queries() == few
