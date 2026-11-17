"""Configurable scoring (story #40): how candidate hospitals are ordered, by rules a coordinator can explain.

Each factor is a value from 0 to 1 on a fixed scale, so a value means the same in every search. A strategy
weights its factors, and the score is the weighted average on a 0 to 100 scale. Strategies are
interchangeable: each resource type gets one, chosen and weighted by the MATCHING_SCORING setting
(see config/settings.py).

config/settings.py imports this module, so it must not import models at module level.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone

if TYPE_CHECKING:
    from apps.emergencies.models import RequestItem

    from .candidates import Candidate, ItemCandidates

BLOOD_GROUP_COUNT = 8  # the groups in BloodGroup; the compatibility factor falls over their ranks

# The default strategy per resource type. The keys are ResourceType's values (a test checks this). They
# live here, not read from the models, so settings.py can validate MATCHING_SCORING without loading apps.
DEFAULT_STRATEGY = {
    "blood": "earliestExpiry",
    "bed": "nearest",
    "equipment": "nearest",
    "operatingRoom": "nearest",
}


def distance_factor(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> float:
    if candidate.distance_km is None:
        return 0.0
    return 1 - min(candidate.distance_km / settings.MATCHING_MAX_DISTANCE_KM, 1.0)


def expiry_factor(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> float:
    if candidate.earliest_expiry is None:
        return 0.0
    # Imported here, not at the top: this module is loaded by settings.py, before the apps are.
    from apps.blood.serializers import SHELF_LIFE_DAYS

    days_left = max((candidate.earliest_expiry - now).total_seconds() / 86400, 0.0)
    return 1 - min(days_left / SHELF_LIFE_DAYS[item.component], 1.0)


def quantity_factor(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> float:
    return min(candidate.available / needed, 1.0)


def compatibility_factor(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> float:
    if candidate.best_donor_rank is None:
        return 0.0
    return 1 - candidate.best_donor_rank / BLOOD_GROUP_COUNT


FACTORS: dict[str, Callable[..., float]] = {
    "distance": distance_factor,
    "expiry": expiry_factor,
    "quantity": quantity_factor,
    "compatibility": compatibility_factor,
}

FACTOR_LABELS: dict[str, str] = {
    "distance": "Distance",
    "expiry": "Expiry",
    "quantity": "Stock",
    "compatibility": "Blood group match",
}


# Each detail is the short reason a factor shows on screen, next to its points.


def distance_detail(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> str:
    if candidate.distance_km is None:
        return "distance unknown"
    return f"{candidate.distance_km:.1f} km, about {candidate.travel_minutes} min"


def expiry_detail(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> str:
    if candidate.earliest_expiry is None:
        return "no expiry date"
    days = (candidate.earliest_expiry - now).total_seconds() / 86400
    if days < 0:
        return "already expired"
    if days < 1:
        return "expires within a day"
    whole = round(days)  # nearest day: a unit due in 9 days reads 9 even a few milliseconds later
    return f"expires in {whole} day" + ("" if whole == 1 else "s")


def quantity_detail(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> str:
    return f"{candidate.available} available, {needed} needed"


def compatibility_detail(candidate: Candidate, *, needed: int, item: RequestItem, now: datetime) -> str:
    if candidate.best_donor_rank is None:
        return "no compatible units"
    if candidate.best_donor_rank == 0:
        return "identical group"
    return f"compatible substitute, rank {candidate.best_donor_rank}"


DETAILS: dict[str, Callable[..., str]] = {
    "distance": distance_detail,
    "expiry": expiry_detail,
    "quantity": quantity_detail,
    "compatibility": compatibility_detail,
}


@dataclass(frozen=True)
class FactorScore:
    name: str
    value: float  # 0 to 1
    weight: float
    points: float  # value x weight, as a share of the total weight, on 0 to 100, to one decimal
    detail: str = ""


@dataclass(frozen=True)
class Score:
    total: float  # 0 to 100, to one decimal: the sum of the factors' points
    factors: tuple[FactorScore, ...]
    strategy: str = ""  # the strategy's name


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: Score
    rank: int = 0  # 1-based position in the ranking; 0 until rank() sets it


def resolve_weights(strategy: type[ScoringStrategy], given: Mapping, *, where: str) -> dict[str, float]:
    """The strategy's weights with `given` merged over its defaults, validated. `where` names the setting's
    part in the error message."""

    def bad(problem: str) -> ImproperlyConfigured:
        return ImproperlyConfigured(f"MATCHING_SCORING ({where}): {problem}")

    for name, value in given.items():
        if name not in strategy.default_weights:
            uses = ", ".join(strategy.default_weights)
            raise bad(f"strategy {strategy.name} does not use the factor {name!r}; it uses {uses}.")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise bad(f"the weight for {name!r} must be a number of 0 or more, not {value!r}.")
    weights = {**strategy.default_weights, **given}
    if sum(weights.values()) <= 0:
        raise bad("all weights are zero; at least one must be above zero.")
    return {name: float(weights[name]) for name in strategy.default_weights}


class ScoringStrategy:
    name: str = ""
    label: str = ""  # for people: how the list is ordered
    default_weights: Mapping[str, float] = {}

    def __init__(self, weights: Mapping[str, float] | None = None):
        self.weights = resolve_weights(type(self), weights or {}, where=f"strategy {self.name}")

    @property
    def factors(self) -> tuple[str, ...]:
        return tuple(self.default_weights)

    def score(
        self, candidate: Candidate, *, needed: int, item: RequestItem, now: datetime | None = None
    ) -> Score:
        now = timezone.now() if now is None else now
        total_weight = sum(self.weights.values())
        factors = []
        for name in self.factors:
            value = FACTORS[name](candidate, needed=needed, item=item, now=now)
            weight = self.weights[name]
            # Rounded before they are added, so the points a reader sees add up to the total.
            points = round(value * weight * 100 / total_weight, 1)
            detail = DETAILS[name](candidate, needed=needed, item=item, now=now)
            factors.append(FactorScore(name, value, weight, points, detail))
        total = round(sum(f.points for f in factors), 1)
        return Score(total=total, factors=tuple(factors), strategy=self.name)


class EarliestExpiryFirst(ScoringStrategy):
    name = "earliestExpiry"
    label = "Earliest expiry first"
    default_weights = {"expiry": 0.5, "compatibility": 0.2, "distance": 0.2, "quantity": 0.1}


class NearestFirst(ScoringStrategy):
    name = "nearest"
    label = "Nearest first"
    default_weights = {"distance": 0.7, "quantity": 0.3}


class MostStockFirst(ScoringStrategy):
    name = "mostStock"
    label = "Most stock first"
    default_weights = {"quantity": 0.7, "distance": 0.3}


STRATEGIES: dict[str, type[ScoringStrategy]] = {
    cls.name: cls for cls in (EarliestExpiryFirst, NearestFirst, MostStockFirst)
}


def parse_scoring_config(raw: str) -> dict[str, dict]:
    """The MATCHING_SCORING setting: JSON keyed by resource type, merged over the defaults and validated.

    Returns {resource type: {"strategy": name, "weights": {factor: weight}}} for every type. Raises
    ImproperlyConfigured, naming the problem, for anything wrong.
    """
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError as exc:
        raise ImproperlyConfigured(f"MATCHING_SCORING is not valid JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ImproperlyConfigured("MATCHING_SCORING must be a JSON object keyed by resource type.")
    for resource_type in data:
        if resource_type not in DEFAULT_STRATEGY:
            known = ", ".join(DEFAULT_STRATEGY)
            raise ImproperlyConfigured(
                f"MATCHING_SCORING: unknown resource type {resource_type!r}; use {known}."
            )

    config = {}
    for resource_type, default_name in DEFAULT_STRATEGY.items():
        entry = data.get(resource_type, {})
        if not isinstance(entry, dict) or not set(entry) <= {"strategy", "weights"}:
            raise ImproperlyConfigured(
                f"MATCHING_SCORING ({resource_type}): use an object with 'strategy' and 'weights' only."
            )
        name = entry.get("strategy", default_name)
        if not isinstance(name, str) or name not in STRATEGIES:
            known = ", ".join(STRATEGIES)
            raise ImproperlyConfigured(
                f"MATCHING_SCORING ({resource_type}): unknown strategy {name!r}; use {known}."
            )
        weights = entry.get("weights", {})
        if not isinstance(weights, dict):
            raise ImproperlyConfigured(
                f"MATCHING_SCORING ({resource_type}): 'weights' must be an object of factor to weight."
            )
        config[resource_type] = {
            "strategy": name,
            "weights": resolve_weights(STRATEGIES[name], weights, where=resource_type),
        }
    return config


def strategy_for(resource_type: str) -> ScoringStrategy:
    """The configured strategy for a resource type, with its configured weights."""
    chosen = settings.MATCHING_SCORING[resource_type]
    return STRATEGIES[chosen["strategy"]](chosen["weights"])


def rank(item_candidates: ItemCandidates, *, now: datetime | None = None) -> list[ScoredCandidate]:
    """The candidates for one requirement with their scores: total descending, then nearest first (no distance
    last), then hospital id. Deterministic on ties."""
    item = item_candidates.item
    strategy = strategy_for(item.resource_type)
    now = timezone.now() if now is None else now
    scored = [
        ScoredCandidate(
            candidate,
            strategy.score(candidate, needed=item_candidates.shortfall, item=item, now=now),
        )
        for candidate in item_candidates.candidates
    ]
    scored.sort(
        key=lambda s: (
            -s.score.total,
            s.candidate.distance_km is None,
            s.candidate.distance_km or 0.0,
            s.candidate.hospital.pk,
        )
    )
    return [replace(s, rank=position) for position, s in enumerate(scored, 1)]
