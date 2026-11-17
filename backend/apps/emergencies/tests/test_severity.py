"""Story #31: severity levels, the order lists sort by, and the migration that renamed the old levels."""

import importlib
from datetime import timedelta

import pytest
from django.apps import apps as installed_apps
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Role
from apps.emergencies.models import EmergencyRequest

pytestmark = pytest.mark.django_db

BED_ITEM = {"type": "bed", "bedType": "icu", "quantity": 1}
migration = importlib.import_module("apps.emergencies.migrations.0003_severity_levels")


def make_case(reference: str, severity: str, hours_ago: float) -> None:
    case = EmergencyRequest.objects.create(reference=reference, severity=severity)
    EmergencyRequest.objects.filter(pk=case.pk).update(created_at=timezone.now() - timedelta(hours=hours_ago))


def severities() -> dict[str, str]:
    return dict(EmergencyRequest.objects.values_list("reference", "severity"))


# ── Migration 0003: urgent → high, routine → moderate (and back) ─────────────────────────────────


def test_forward_renames_urgent_to_high_and_routine_to_moderate():
    for reference, severity in [("EC-1", "critical"), ("EC-2", "urgent"), ("EC-3", "routine")]:
        EmergencyRequest.objects.create(reference=reference, severity=severity)

    migration.remap(migration.FORWARD)(installed_apps, None)

    assert severities() == {"EC-1": "critical", "EC-2": "high", "EC-3": "moderate"}


def test_backward_maps_high_to_urgent_and_moderate_or_low_to_routine():
    for reference, severity in [
        ("EC-1", "critical"),
        ("EC-2", "high"),
        ("EC-3", "moderate"),
        ("EC-4", "low"),
    ]:
        EmergencyRequest.objects.create(reference=reference, severity=severity)

    migration.remap(migration.BACKWARD)(installed_apps, None)

    assert severities() == {"EC-1": "critical", "EC-2": "urgent", "EC-3": "routine", "EC-4": "routine"}


# ── Ordering: most severe first, then the case waiting longest ───────────────────────────────────


def test_lists_are_most_severe_first_then_oldest_first(client_as):
    # Ids and insertion order deliberately disagree with the expected order: age and severity decide it.
    make_case("EC-2026-0001", "low", hours_ago=30)
    make_case("EC-2026-0002", "moderate", hours_ago=2)
    make_case("EC-2026-0003", "critical", hours_ago=1)
    make_case("EC-2026-0004", "high", hours_ago=3)
    make_case("EC-2026-0005", "critical", hours_ago=4)
    make_case("EC-2026-0006", "low", hours_ago=60)
    make_case("EC-2026-0007", "moderate", hours_ago=9)

    res = client_as(Role.ADMIN).get(reverse("emergency-cases"))

    assert [c["id"] for c in res.json()] == [
        "EC-2026-0005",  # critical, waiting 4 h
        "EC-2026-0003",  # critical, waiting 1 h
        "EC-2026-0004",  # high
        "EC-2026-0007",  # moderate, waiting 9 h
        "EC-2026-0002",  # moderate, waiting 2 h
        "EC-2026-0006",  # low, waiting 60 h
        "EC-2026-0001",  # low, waiting 30 h
    ]


# ── Levels accepted and refused ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("level", ["critical", "high", "moderate", "low"])
def test_each_level_is_accepted(client_as, level):
    res = client_as(Role.DOCTOR).post(
        reverse("emergency-cases"), {"severity": level, "items": [BED_ITEM]}, format="json"
    )
    assert res.status_code == 201 and res.json()["severity"] == level


@pytest.mark.parametrize("level", ["urgent", "routine", "Critical", ""])
def test_the_old_or_unknown_levels_are_refused(client_as, level):
    res = client_as(Role.DOCTOR).post(
        reverse("emergency-cases"), {"severity": level, "items": [BED_ITEM]}, format="json"
    )
    assert res.status_code == 400 and "severity" in res.json()
    assert not EmergencyRequest.objects.exists()
