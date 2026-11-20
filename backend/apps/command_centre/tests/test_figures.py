"""Story #55: the figures per hospital, the shortage levels, the network totals, and what is left out."""

import json
import re
from datetime import datetime
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.blood.models import BloodUnit, Component
from apps.blood.services import RED_CELL_MINIMUM, stock_summary
from apps.command_centre.services import network_figures
from apps.emergencies.models import ResourceType
from apps.equipment.models import EquipmentType
from apps.hospitals.models import BedType
from apps.matching.models import ReservationStatus
from apps.matching.tests.reservation_support import blood_need, case, hold, staff, unit

from .support import empty_hospital, fully_stocked, stocked_hospital

pytestmark = pytest.mark.django_db

FRONTEND_BLOOD = Path(__file__).resolve().parents[4] / "frontend" / "src" / "api" / "blood.ts"


@pytest.fixture
def network(make_hospital, make_user):
    civic = make_hospital("Civic General")
    bay = make_hospital("Bay Children's")
    stocked_hospital(civic, make_user)
    empty_hospital(bay, make_user)
    return network_figures()


def row(figures, name):
    return next(h for h in figures["hospitals"] if h["name"] == name)


def red(hospital_row, group):
    return next(r for r in hospital_row["redCells"] if r["group"] == group)


# ── Per hospital ───────────────────────────────────────────────────────────────────────────────


def test_each_hospital_has_its_own_figures(network):
    civic = row(network, "Civic General")
    assert red(civic, "A-") == {"group": "A-", "available": 1, "minimum": 4, "level": "critical"}
    assert red(civic, "O+")["available"] == 1
    assert civic["components"]["redCells"] == {"usable": 2, "nearExpiry": 1}
    assert civic["components"]["plasma"] == {"usable": 1, "nearExpiry": 0}
    assert civic["components"]["platelets"] == {"usable": 0, "nearExpiry": 0}
    assert civic["beds"] == {"icu": 2, "emergency": 0, "general": 0, "isolation": 1, "nicu": 0}
    assert civic["equipment"] == {"ventilator": 1, "monitor": 1, "defibrillator": 0, "dialysis": 0}
    assert civic["operatingRooms"] == 1
    assert civic["cases"] == {"active": 2, "escalated": 1}
    assert civic["open"] == {"blood": 3, "bed": 2, "equipment": 0, "operatingRoom": 0}


def test_a_hospital_without_stock_has_zero_rows_and_its_open_need(network):
    bay = row(network, "Bay Children's")
    assert all(r["available"] == 0 and r["level"] == "critical" for r in bay["redCells"])
    assert bay["components"]["cryo"] == {"usable": 0, "nearExpiry": 0}
    assert bay["beds"] == dict.fromkeys(BedType.values, 0)
    assert bay["equipment"] == dict.fromkeys(EquipmentType.values, 0)
    assert bay["operatingRooms"] == 0
    assert bay["cases"] == {"active": 1, "escalated": 0}
    assert bay["open"] == {"blood": 0, "bed": 1, "equipment": 0, "operatingRoom": 0}


@pytest.mark.parametrize(
    ("count", "level"),
    [(0, "critical"), (1, "critical"), (2, "low"), (3, "low"), (4, "ok"), (9, "ok")],
)
def test_red_cell_shortage_level_for_a_minimum_of_four(make_hospital, count, level):
    """A- has a minimum of 4: critical below 2 (half), low below 4, ok from 4 up."""
    hospital = make_hospital("Level Test")
    for _ in range(count):
        unit(hospital, group="A-")
    assert red(row(network_figures(), "Level Test"), "A-") == {
        "group": "A-",
        "available": count,
        "minimum": 4,
        "level": level,
    }


def test_near_expiry_counts_usable_units_inside_the_window(make_hospital):
    hospital = make_hospital("Window")
    near = settings.BLOOD_NEAR_EXPIRY_DAYS
    unit(hospital, component="plasma", expires_in_days=near - 1)  # near
    unit(hospital, component="plasma", expires_in_days=near + 1)  # not near
    unit(hospital, component="plasma", expires_in_days=-1)  # past expiry: not usable at all
    figures = network_figures()
    assert row(figures, "Window")["components"]["plasma"] == {"usable": 2, "nearExpiry": 1}
    assert figures["nearExpiryDays"] == near


def test_open_need_leaves_out_allocated_holds_already_in_fulfilled(make_hospital, make_user):
    """Quantity 2, one already allocated (fulfilled 1, its hold allocated): one still open, not two."""
    hospital = make_hospital("Allocated")
    nurse = staff(make_user, hospital)
    needed = case(hospital, blood_need("A+", quantity=2, fulfilled=1), status="partiallyFulfilled")
    item = needed.items.get()
    hold(item, unit(hospital, group="A+"), hospital=hospital, actor=nurse, status=ReservationStatus.ALLOCATED)
    assert row(network_figures(), "Allocated")["open"]["blood"] == 1


# ── Network totals ─────────────────────────────────────────────────────────────────────────────


def test_totals_are_the_sums_of_the_hospital_rows(network):
    rows, totals = network["hospitals"], network["totals"]
    assert [t["available"] for t in totals["redCells"]] == [
        sum(h["redCells"][i]["available"] for h in rows) for i in range(len(RED_CELL_MINIMUM))
    ]
    assert totals["redCells"][2] == {"group": "A-", "available": 1}
    for component in Component.values:
        for field in ("usable", "nearExpiry"):
            assert totals["components"][component][field] == sum(
                h["components"][component][field] for h in rows
            )
    assert totals["beds"] == {"icu": 2, "emergency": 0, "general": 0, "isolation": 1, "nicu": 0}
    assert totals["equipment"] == {"ventilator": 1, "monitor": 1, "defibrillator": 0, "dialysis": 0}
    assert totals["operatingRooms"] == 1
    assert totals["cases"] == {"active": 3, "escalated": 1}
    assert totals["open"] == {"blood": 3, "bed": 3, "equipment": 0, "operatingRoom": 0}


def test_an_empty_network_has_zero_totals_and_no_rows():
    figures = network_figures()
    assert figures["hospitals"] == []
    assert figures["totals"]["redCells"] == [{"group": g, "available": 0} for g in RED_CELL_MINIMUM]
    assert figures["totals"]["beds"] == dict.fromkeys(BedType.values, 0)
    assert figures["totals"]["open"] == dict.fromkeys(ResourceType.values, 0)


def test_inactive_hospitals_are_left_out_of_rows_and_totals(network, make_hospital, make_user):
    closed = make_hospital("Old Wing", is_active=False)
    stocked_hospital(closed, make_user)  # stock, beds, rooms and cases, all of them ignored
    figures = network_figures()
    assert "Old Wing" not in [h["name"] for h in figures["hospitals"]]
    assert figures["totals"] == network["totals"]


# ── Ordering and the shortage rule ─────────────────────────────────────────────────────────────


def test_hospitals_with_a_critical_shortage_come_first_then_by_name(make_hospital, make_user):
    stocked_hospital(make_hospital("Civic General"), make_user)
    empty_hospital(make_hospital("Bay Children's"), make_user)
    fully_stocked(make_hospital("Alpha Clinic"))  # every group at its minimum: no shortage at all
    names = [h["name"] for h in network_figures()["hospitals"]]
    assert names == ["Bay Children's", "Civic General", "Alpha Clinic"]


def test_figures_carry_the_time_they_were_taken(network):
    assert network["updatedAt"]
    assert datetime.fromisoformat(network["updatedAt"]).tzinfo is not None


# ── Agreement with the Blood page and the frontend ─────────────────────────────────────────────


def test_red_cells_match_the_blood_pages_stock_summary_on_the_seeded_network():
    call_command("seed_demo", stdout=StringIO())
    now = timezone.now()
    figures = network_figures(now=now)
    assert any(r["available"] for h in figures["hospitals"] for r in h["redCells"])
    for entry in figures["hospitals"]:
        summary = stock_summary(
            BloodUnit.objects.filter(hospital_id=entry["id"]),
            near_expiry_days=settings.BLOOD_NEAR_EXPIRY_DAYS,
            low_stock_units=settings.BLOOD_LOW_STOCK_UNITS,
            now=now,
        )
        red_rows = {r["group"]: r for r in summary["rows"] if r["component"] == Component.RED_CELLS}
        for entry_red in entry["redCells"]:
            assert entry_red["available"] == red_rows[entry_red["group"]]["available"]
        assert entry["components"]["redCells"]["nearExpiry"] == sum(
            r["nearExpiry"] for r in red_rows.values()
        )


def test_red_cell_minimums_match_the_frontend_copy():
    """blood.ts keeps MINIMUM_STOCK; this copy must say the same numbers (story #55, open question 6)."""
    text = FRONTEND_BLOOD.read_text(encoding="utf-8")
    body = re.search(r"redCells: \{([^}]*)\}", text).group(1)
    frontend = {group: int(value) for group, value in re.findall(r"'([^']+)':\s*(\d+)", body)}
    assert frontend == RED_CELL_MINIMUM


# ── Privacy ────────────────────────────────────────────────────────────────────────────────────

ALLOWED_KEYS = {
    "updatedAt",
    "nearExpiryDays",
    "totals",
    "hospitals",
    "id",
    "name",
    "redCells",
    "group",
    "available",
    "minimum",
    "level",
    "components",
    "usable",
    "nearExpiry",
    "beds",
    "equipment",
    "operatingRooms",
    "cases",
    "active",
    "escalated",
    "open",
    *BedType.values,
    *EquipmentType.values,
    *Component.values,
    *ResourceType.values,
}


def keys_in(value):
    if isinstance(value, dict):
        for key, inner in value.items():
            yield key
            yield from keys_in(inner)
    elif isinstance(value, list):
        for item in value:
            yield from keys_in(item)


def test_only_counts_and_hospital_names_leave_the_server(network):
    """No patient field, case reference, unit or asset identifier, or staff name."""
    assert set(keys_in(network)) <= ALLOWED_KEYS
    text = json.dumps(network)
    assert "EC-" not in text and "DN-" not in text and "VENT-" not in text
