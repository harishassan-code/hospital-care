"""Stories #18 (collection and testing status) and #19 (expiry alerts and stock levels)."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.audit.models import AuditLog
from apps.blood.models import REQUIRED_TESTS, BloodUnit, UnitStatus

pytestmark = pytest.mark.django_db


def make_unit(
    number="U1", status=UnitStatus.QUARANTINED, expires_in=30, group="O-", component="redCells", **extra
):
    now = timezone.now()
    return BloodUnit.objects.create(
        donation_number=number, group=group, component=component, collected_at=now - timedelta(days=10),
        expires_at=now + timedelta(days=expires_in), status=status, location="Blood fridge 1", **extra,
    )  # fmt: skip


def post_test(client, number, test, passed=True, reason=""):
    return client.post(
        reverse("blood-unit-tests", args=[number]),
        {"test": test, "passed": passed, "reason": reason},
        format="json",
    )


@pytest.fixture
def staff(client_as):
    return client_as(Role.BLOOD_BANK)


# ── #18 Collection and testing ──────────────────────────────────────────────────────────────────


def test_unit_stays_quarantined_until_every_test_passes_then_is_released(staff):
    make_unit()
    for test in REQUIRED_TESTS[:-1]:
        data = post_test(staff, "U1", test).json()
        assert data["status"] == "quarantined"
    assert data["missingTests"] == [REQUIRED_TESTS[-1]]

    data = post_test(staff, "U1", REQUIRED_TESTS[-1]).json()
    assert data["status"] == "available" and data["missingTests"] == []
    assert len(data["tests"]) == len(REQUIRED_TESTS)


def test_failed_test_discards_the_unit_with_the_reason_in_the_audit_log(staff):
    make_unit()
    res = post_test(staff, "U1", "hbv", passed=False, reason="HBsAg reactive")
    assert res.status_code == 201 and res.json()["status"] == "discarded"
    entry = AuditLog.objects.filter(action="bloodunit.status_changed").latest("id")
    assert entry.after == {"status": "discarded"} and "HBsAg reactive" in entry.reason


def test_failed_test_needs_a_reason(staff):
    make_unit()
    assert post_test(staff, "U1", "hiv", passed=False).status_code == 400
    assert BloodUnit.objects.get().status == UnitStatus.QUARANTINED


def test_same_test_twice_and_tests_on_a_released_unit_are_refused(staff):
    make_unit()
    post_test(staff, "U1", "hiv")
    assert post_test(staff, "U1", "hiv").status_code == 400
    make_unit("U2", status=UnitStatus.AVAILABLE)
    assert post_test(staff, "U2", "hiv").status_code == 409


def test_release_by_hand_needs_every_test_and_discard_needs_a_reason(staff):
    make_unit()
    url = reverse("blood-unit-action", args=["U1"])
    assert staff.post(url, {"action": "release"}, format="json").status_code == 409
    assert staff.post(url, {"action": "discard"}, format="json").status_code == 400
    res = staff.post(url, {"action": "discard", "reason": "Bag leaking"}, format="json")
    assert res.json()["status"] == "discarded"


def test_only_available_unexpired_units_appear_in_a_search(staff):
    make_unit("Q", status=UnitStatus.QUARANTINED)
    make_unit("A", status=UnitStatus.AVAILABLE)
    make_unit("OLD", status=UnitStatus.AVAILABLE, expires_in=-1)
    make_unit("D", status=UnitStatus.DISCARDED)
    found = staff.get(reverse("blood-units"), {"status": "available", "group": "O-"}).json()
    assert [u["id"] for u in found] == ["A"]


def test_doctor_can_read_units_but_not_record_tests(client_as):
    make_unit()
    doctor = client_as(Role.DOCTOR)
    assert doctor.get(reverse("blood-unit", args=["U1"])).status_code == 200
    assert post_test(doctor, "U1", "hiv").status_code == 403


def test_staff_cannot_test_another_hospitals_unit(client_as, make_hospital):
    mine, theirs = make_hospital("Mine"), make_hospital("Theirs")
    make_unit(hospital=theirs)
    assert post_test(client_as(Role.BLOOD_BANK, hospital=mine), "U1", "hiv").status_code == 403


# ── #19 Expiry and stock ────────────────────────────────────────────────────────────────────────


def test_units_past_expiry_are_marked_expired_and_logged():
    make_unit("OLD", status=UnitStatus.AVAILABLE, expires_in=-1)
    make_unit("NEW", status=UnitStatus.AVAILABLE)
    make_unit("GONE", status=UnitStatus.ISSUED, expires_in=-1)
    call_command("expire_blood_units", stdout=None)
    statuses = dict(BloodUnit.objects.values_list("donation_number", "status"))
    assert statuses == {"OLD": "expired", "NEW": "available", "GONE": "issued"}
    assert AuditLog.objects.filter(action="bloodunit.status_changed", actor=None).count() == 1


def test_stock_counts_per_group_and_component_with_low_stock_and_near_expiry(staff, settings):
    settings.BLOOD_LOW_STOCK_UNITS = 2
    make_unit("A1", status=UnitStatus.AVAILABLE, expires_in=2)
    make_unit("A2", status=UnitStatus.AVAILABLE, expires_in=20)
    make_unit("R1", status=UnitStatus.RESERVED)
    make_unit("B1", status=UnitStatus.AVAILABLE, group="B+")

    data = staff.get(reverse("blood-stock")).json()
    assert data["nearExpiryDays"] == 3 and data["lowStockUnits"] == 2
    rows = {(r["group"], r["component"]): r for r in data["rows"]}
    assert len(rows) == 8 * 4
    assert rows[("O-", "redCells")] == {
        "group": "O-", "component": "redCells", "available": 2, "reserved": 1, "quarantined": 0,
        "nearExpiry": 1, "low": False,
    }  # fmt: skip
    assert rows[("B+", "redCells")]["low"] is True
    assert [u["id"] for u in data["nearExpiryUnits"]] == ["A1"]


def test_near_expiry_threshold_is_configurable(staff):
    make_unit("A1", status=UnitStatus.AVAILABLE, expires_in=5)
    assert staff.get(reverse("blood-stock")).json()["nearExpiryUnits"] == []
    data = staff.get(reverse("blood-stock"), {"nearExpiryDays": 7}).json()
    assert [u["id"] for u in data["nearExpiryUnits"]] == ["A1"]
    assert staff.get(reverse("blood-stock"), {"nearExpiryDays": "soon"}).status_code == 400


def test_stock_view_expires_overdue_units_first(staff):
    make_unit("OLD", status=UnitStatus.AVAILABLE, expires_in=-1)
    rows = staff.get(reverse("blood-stock")).json()["rows"]
    assert sum(r["available"] for r in rows) == 0
    assert BloodUnit.objects.get().status == UnitStatus.EXPIRED
