"""B18 (#66): the report figures on fixed data, the range rules and their edges."""

import datetime as dt

import pytest

from apps.blood.models import UnitStatus
from apps.matching.tests.reservation_support import blood_need, equipment_need, staff, unit
from apps.reports import services
from apps.reports.services import ReportQueryError, ReportRange, range_from

from .support import allocated, blood_unit, fulfilled, opened, when

pytestmark = pytest.mark.django_db

NOVEMBER = (dt.date(2026, 11, 1), dt.date(2026, 11, 10))
NOW = when("2026-11-20T12:00:00+05:00")


def november(hospital=None) -> ReportRange:
    return ReportRange(*NOVEMBER, hospital)


# ── The range ────────────────────────────────────────────────────────────────────────────────────────

TODAY = dt.date(2026, 11, 20)


def test_no_dates_means_the_30_days_ending_today():
    r = range_from({}, today=TODAY)
    assert (r.start, r.end, r.days) == (dt.date(2026, 10, 22), TODAY, 30)


def test_only_from_runs_to_today_and_only_to_covers_the_30_days_before_it():
    assert range_from({"from": "2026-11-01"}, today=TODAY).end == TODAY
    r = range_from({"to": "2026-11-10"}, today=TODAY)
    assert (r.start, r.end) == (dt.date(2026, 10, 12), dt.date(2026, 11, 10))


def test_366_days_is_allowed_and_367_is_refused():
    assert range_from({"from": "2025-11-20", "to": "2026-11-20"}).days == 366
    with pytest.raises(ReportQueryError, match="at most 366 days"):
        range_from({"from": "2025-11-19", "to": "2026-11-20"})


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"from": "2026-11-10", "to": "2026-11-01"}, "or later"),
        ({"from": "1/11/2026"}, "YYYY-MM-DD"),
        ({"to": "2026-02-30"}, "real date"),
        ({"hospital": "abc"}, "hospital id"),
        ({"hospital": "999"}, "No hospital"),
    ],
)
def test_bad_ranges_and_filters_are_refused(params, message):
    with pytest.raises(ReportQueryError, match=message):
        range_from(params, today=TODAY)


def test_days_are_karachi_days(make_hospital):
    r = november()
    assert r.lower == when("2026-11-01T00:00:00+05:00")
    assert r.upper == when("2026-11-11T00:00:00+05:00")


# ── Requests ─────────────────────────────────────────────────────────────────────────────────────────


def test_requests_counts_cases_opened_in_the_range_with_their_needs_and_allocations(make_hospital, make_user):
    general, other = make_hospital(), make_hospital("Seaview Hospital")
    nurse = staff(make_user, general)
    first = opened(
        general,
        "2026-11-01T00:00:00+05:00",  # first moment of the range
        blood_need("O-", quantity=4),
        equipment_need(quantity=1),
        severity="critical",
        status="fulfilled",
    )
    opened(general, "2026-11-10T23:59:00+05:00", blood_need("A+", quantity=2), status="escalated")
    opened(general, "2026-10-31T23:59:00+05:00", blood_need(quantity=9))  # before the range
    opened(general, "2026-11-11T00:00:00+05:00", blood_need(quantity=9))  # after it
    opened(other, "2026-11-05T10:00:00+05:00", equipment_need(quantity=2), severity="low")

    item = first.items.get(resource_type="blood")
    for at in ("2026-11-02T10:00:00+05:00", "2026-11-02T10:05:00+05:00"):
        allocated(item, unit(general, group="O-"), hospital=general, actor=nurse, at=at)
    allocated(item, unit(general, group="O-"), hospital=general, actor=nurse, at="2026-11-12T10:00:00+05:00")

    report = services.requests_report(november())

    assert report["total"] == 3
    assert {row["id"]: row["count"] for row in report["bySeverity"]} == {
        "critical": 1,
        "high": 1,
        "moderate": 0,
        "low": 1,
    }
    statuses = {row["id"]: row["count"] for row in report["byStatus"]}
    assert (statuses["fulfilled"], statuses["escalated"], statuses["open"], statuses["closed"]) == (
        1,
        1,
        1,
        0,
    )
    types = {row["id"]: row for row in report["byResourceType"]}
    assert types["blood"] == {
        "id": "blood",
        "label": "Blood",
        "needs": 2,
        "unitsAsked": 6,
        "unitsAllocated": 2,
    }
    assert (types["equipment"]["needs"], types["equipment"]["unitsAsked"]) == (2, 3)
    assert types["bed"]["needs"] == 0
    assert report["allocations"] == 2

    only_seaview = services.requests_report(november(other))
    assert (only_seaview["total"], only_seaview["allocations"]) == (1, 0)


# ── Fulfilment time ──────────────────────────────────────────────────────────────────────────────────


def test_fulfilment_times_count_each_case_once_by_its_first_fulfilment_in_the_range(make_hospital):
    general = make_hospital()
    a = opened(general, "2026-11-02T10:00:00+05:00", severity="critical")
    fulfilled(a, "2026-11-02T10:30:00+05:00")  # 30 min
    b = opened(general, "2026-11-03T09:00:00+05:00", severity="critical")
    fulfilled(b, "2026-11-03T10:30:00+05:00")  # 90 min
    c = opened(general, "2026-11-04T08:00:00+05:00", severity="high")
    fulfilled(c, "2026-11-04T08:10:00+05:00")  # 10 min
    fulfilled(c, "2026-11-06T08:00:00+05:00")  # reopened and fulfilled again: still counted once
    d = opened(general, "2026-10-31T23:50:00+05:00", severity="high")
    fulfilled(d, "2026-11-01T00:30:00+05:00")  # opened before, fulfilled inside: 40 min, counts
    e = opened(general, "2026-11-10T23:00:00+05:00", severity="high")
    fulfilled(e, "2026-11-11T00:10:00+05:00")  # fulfilled the day after the range: not counted
    opened(general, "2026-11-05T10:00:00+05:00", status="escalated")
    opened(general, "2026-11-05T11:00:00+05:00", status="cancelled")
    opened(general, "2026-11-05T12:00:00+05:00", status="cancelled")

    report = services.fulfilment_report(november())

    assert report["overall"] == {
        "count": 4,
        "medianMinutes": 35.0,
        "averageMinutes": 42.5,
        "p90Minutes": 90.0,
    }
    severity = {row["id"]: row for row in report["bySeverity"]}
    assert (severity["critical"]["count"], severity["critical"]["medianMinutes"]) == (2, 60.0)
    assert (severity["high"]["count"], severity["high"]["averageMinutes"]) == (2, 25.0)
    assert severity["low"] == {"id": "low", "label": "Low", **services._stats([])}
    # e was opened in the range and isn't fulfilled within it, but it was fulfilled: it isn't "never".
    assert report["notFulfilled"] == [
        {"id": "escalated", "label": "Escalated", "count": 1},
        {"id": "cancelled", "label": "Cancelled", "count": 2},
    ]


def test_nearest_rank_percentile():
    assert services.percentile([5.0], 0.9) == 5.0
    assert services.percentile([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], 0.9) == 9.0
    assert services.percentile([10.0, 1.0, 5.0], 0.5) == 5.0


# ── Wastage ──────────────────────────────────────────────────────────────────────────────────────────


def test_wastage_counts_units_that_expired_unused_or_were_discarded_in_the_range(make_hospital):
    general, other = make_hospital(), make_hospital("Seaview Hospital")
    blood_unit(general, expires="2026-11-02T08:00:00+05:00", status=UnitStatus.EXPIRED)
    blood_unit(
        general, expires="2026-11-10T23:59:00+05:00", status=UnitStatus.AVAILABLE
    )  # on the shelf, past it
    blood_unit(general, expires="2026-11-10T23:59:00+05:00", status=UnitStatus.RESERVED, component="plasma")
    blood_unit(general, expires="2026-11-03T08:00:00+05:00", status=UnitStatus.ISSUED)  # used: not waste
    blood_unit(general, expires="2026-11-11T00:00:00+05:00", status=UnitStatus.EXPIRED)  # after the range
    blood_unit(
        general,
        expires="2026-12-20T08:00:00+05:00",
        status=UnitStatus.DISCARDED,
        since="2026-11-04T09:00:00+05:00",
    )
    blood_unit(
        general,
        expires="2026-12-20T08:00:00+05:00",
        status=UnitStatus.DISCARDED,
        since="2026-10-30T09:00:00+05:00",  # discarded before the range
    )
    blood_unit(other, expires="2026-11-05T08:00:00+05:00", status=UnitStatus.EXPIRED, group="A+")

    report = services.wastage_report(november(), now=NOW)

    assert (report["expired"], report["discarded"]) == (4, 1)
    assert report["rows"] == [
        {
            "hospital": "CityCare General Hospital",
            "group": "O-",
            "component": "plasma",
            "expired": 1,
            "discarded": 0,
        },
        {
            "hospital": "CityCare General Hospital",
            "group": "O-",
            "component": "redCells",
            "expired": 2,
            "discarded": 1,
        },
        {
            "hospital": "Seaview Hospital",
            "group": "A+",
            "component": "redCells",
            "expired": 1,
            "discarded": 0,
        },
    ]
    assert services.wastage_report(november(other), now=NOW)["expired"] == 1


def test_a_unit_whose_expiry_is_still_ahead_is_not_waste_yet(make_hospital):
    general = make_hospital()
    blood_unit(general, expires="2026-11-09T12:00:00+05:00")
    report = services.wastage_report(november(), now=when("2026-11-08T12:00:00+05:00"))
    assert report["expired"] == 0


def test_build_puts_the_three_reports_under_the_range(make_hospital):
    general = make_hospital()
    report = services.build(november(general))
    assert report["range"] == {"from": "2026-11-01", "to": "2026-11-10", "days": 10}
    assert report["hospital"] == {"id": general.pk, "name": general.name}
    assert set(report) >= {"generatedAt", "requests", "fulfilment", "wastage"}
