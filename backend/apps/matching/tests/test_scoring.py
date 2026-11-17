"""Story #40: configurable scoring of candidate hospitals. Pure logic: no database."""

import itertools
from datetime import timedelta

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from django.utils import timezone

from apps.blood.models import Component
from apps.emergencies.models import RequestItem, ResourceType
from apps.hospitals.models import Hospital
from apps.matching.candidates import Candidate, ItemCandidates
from apps.matching.scoring import (
    DEFAULT_STRATEGY,
    DETAILS,
    STRATEGIES,
    EarliestExpiryFirst,
    MostStockFirst,
    NearestFirst,
    compatibility_detail,
    compatibility_factor,
    distance_detail,
    distance_factor,
    expiry_detail,
    expiry_factor,
    parse_scoring_config,
    quantity_factor,
    rank,
    strategy_for,
)

NOW = timezone.now()


@pytest.fixture(autouse=True)
def defaults():
    """The defaults, whatever the environment says."""
    with override_settings(MATCHING_SCORING=parse_scoring_config(""), MATCHING_MAX_DISTANCE_KM=50):
        yield


def blood_item(component=Component.RED_CELLS):
    return RequestItem(resource_type=ResourceType.BLOOD, blood_group="A+", component=component, quantity=3)


def bed_item():
    return RequestItem(resource_type=ResourceType.BED, bed_type="icu", quantity=3)


def candidate(pk=1, *, available=5, distance_km=10.0, expires_in=None, donor_rank=None):
    return Candidate(
        hospital=Hospital(pk=pk),
        available=available,
        covers=available >= 3,
        distance_km=distance_km,
        travel_minutes=None,
        earliest_expiry=None if expires_in is None else NOW + timedelta(days=expires_in),
        best_donor_rank=donor_rank,
    )


def ranked(item, shortfall, *candidates):
    return rank(ItemCandidates(item=item, shortfall=shortfall, candidates=list(candidates)), now=NOW)


# Factor edges.


@pytest.mark.parametrize(
    ("km", "expected"),
    [(0, 1.0), (25, 0.5), (50, 0.0), (80, 0.0), (None, 0.0)],
)
def test_distance_factor_edges(km, expected):
    value = distance_factor(candidate(distance_km=km), needed=3, item=blood_item(), now=NOW)
    assert value == pytest.approx(expected)


def test_distance_maximum_is_configurable():
    with override_settings(MATCHING_MAX_DISTANCE_KM=100):
        value = distance_factor(candidate(distance_km=50), needed=3, item=blood_item(), now=NOW)
    assert value == pytest.approx(0.5)


@pytest.mark.parametrize(
    ("component", "days", "expected"),
    [
        (Component.RED_CELLS, 0, 1.0),  # expiring now
        (Component.RED_CELLS, 21, 0.5),
        (Component.RED_CELLS, 42, 0.0),  # at the full shelf life
        (Component.PLATELETS, 5, 0.0),  # platelets live 5 days, so their horizon is shorter
        (Component.PLATELETS, 0, 1.0),
    ],
)
def test_expiry_factor_edges(component, days, expected):
    value = expiry_factor(candidate(expires_in=days), needed=3, item=blood_item(component), now=NOW)
    assert value == pytest.approx(expected)


def test_expiry_factor_without_expiry_is_zero():
    assert expiry_factor(candidate(), needed=3, item=blood_item(), now=NOW) == 0.0


@pytest.mark.parametrize(("available", "expected"), [(1, 1 / 3), (3, 1.0), (5, 1.0)])
def test_quantity_factor_below_equal_and_above_need(available, expected):
    value = quantity_factor(candidate(available=available), needed=3, item=blood_item(), now=NOW)
    assert value == pytest.approx(expected)


@pytest.mark.parametrize(("donor_rank", "expected"), [(0, 1.0), (7, 0.125), (None, 0.0)])
def test_compatibility_factor_identical_worst_and_unknown(donor_rank, expected):
    value = compatibility_factor(candidate(donor_rank=donor_rank), needed=3, item=blood_item(), now=NOW)
    assert value == pytest.approx(expected)


# Scores.


@pytest.mark.parametrize(
    ("strategy", "item", "cand"),
    [
        (
            EarliestExpiryFirst,
            blood_item(),
            candidate(available=2, distance_km=20, expires_in=10, donor_rank=2),
        ),
        (NearestFirst, bed_item(), candidate(available=4, distance_km=5)),
        (MostStockFirst, bed_item(), candidate(available=1, distance_km=None)),
    ],
)
def test_points_add_up_to_the_total(strategy, item, cand):
    score = strategy().score(cand, needed=3, item=item, now=NOW)
    total_weight = sum(strategy.default_weights.values())

    assert [f.name for f in score.factors] == list(strategy.default_weights)
    assert score.total == pytest.approx(sum(f.points for f in score.factors), abs=0.05)
    assert 0 <= score.total <= 100
    assert score.strategy == strategy.name
    for factor in score.factors:
        assert factor.points == pytest.approx(factor.value * factor.weight * 100 / total_weight, abs=0.05)
        assert round(factor.points, 1) == factor.points  # one decimal, so the sum shows exactly


def test_the_points_sum_to_the_total_exactly_when_shown_to_one_decimal():
    cand = candidate(available=2, distance_km=20, expires_in=10, donor_rank=2)
    score = EarliestExpiryFirst().score(cand, needed=3, item=blood_item(), now=NOW)
    assert round(sum(f.points for f in score.factors), 1) == score.total


# Details: the short reason shown next to each factor's points.


def test_each_factor_detail_says_the_reason_in_plain_words():
    item = blood_item()
    cand = Candidate(
        hospital=Hospital(pk=1),
        available=4,
        covers=True,
        distance_km=4.24,
        travel_minutes=6,
        earliest_expiry=NOW + timedelta(days=3, hours=5),
        best_donor_rank=0,
    )
    details = {
        name: DETAILS[name](cand, needed=3, item=item, now=NOW)
        for name in ("distance", "expiry", "quantity", "compatibility")
    }
    assert details == {
        "distance": "4.2 km, about 6 min",
        "expiry": "expires in 3 days",
        "quantity": "4 available, 3 needed",
        "compatibility": "identical group",
    }


def test_details_for_the_missing_and_the_unusual_cases():
    item = blood_item()
    unknown = candidate(distance_km=None, expires_in=None, donor_rank=None)
    assert distance_detail(unknown, needed=3, item=item, now=NOW) == "distance unknown"
    assert expiry_detail(unknown, needed=3, item=item, now=NOW) == "no expiry date"
    assert compatibility_detail(unknown, needed=3, item=item, now=NOW) == "no compatible units"

    substitute = candidate(donor_rank=2)
    assert compatibility_detail(substitute, needed=3, item=item, now=NOW) == "compatible substitute, rank 2"
    assert expiry_detail(candidate(expires_in=1), needed=3, item=item, now=NOW) == "expires in 1 day"
    assert expiry_detail(candidate(expires_in=0.5), needed=3, item=item, now=NOW) == "expires within a day"
    assert expiry_detail(candidate(expires_in=-1), needed=3, item=item, now=NOW) == "already expired"


# Defaults and configuration.


def test_defaults_per_resource_type():
    assert DEFAULT_STRATEGY.keys() == set(ResourceType.values)
    assert isinstance(strategy_for(ResourceType.BLOOD), EarliestExpiryFirst)
    for resource_type in (ResourceType.BED, ResourceType.EQUIPMENT, ResourceType.OPERATING_ROOM):
        assert isinstance(strategy_for(resource_type), NearestFirst)


def test_default_weights_of_each_strategy():
    assert EarliestExpiryFirst.default_weights == {
        "expiry": 0.5,
        "compatibility": 0.2,
        "distance": 0.2,
        "quantity": 0.1,
    }
    assert NearestFirst.default_weights == {"distance": 0.7, "quantity": 0.3}
    assert MostStockFirst.default_weights == {"quantity": 0.7, "distance": 0.3}
    assert set(STRATEGIES) == {"earliestExpiry", "nearest", "mostStock"}


def test_a_partial_override_keeps_the_other_defaults():
    config = parse_scoring_config(
        '{"blood": {"weights": {"expiry": 0.6, "distance": 0.4}}, "bed": {"strategy": "mostStock"}}'
    )
    assert config["blood"] == {
        "strategy": "earliestExpiry",
        "weights": {"expiry": 0.6, "compatibility": 0.2, "distance": 0.4, "quantity": 0.1},
    }
    assert config["bed"] == {"strategy": "mostStock", "weights": {"quantity": 0.7, "distance": 0.3}}
    assert config["equipment"] == {"strategy": "nearest", "weights": {"distance": 0.7, "quantity": 0.3}}


def test_weights_from_the_setting_change_the_order_without_code_changes():
    soon_far = candidate(pk=1, distance_km=40, expires_in=1, donor_rank=0)
    late_near = candidate(pk=2, distance_km=2, expires_in=40, donor_rank=0)

    assert ranked(blood_item(), 3, soon_far, late_near)[0].candidate.hospital.pk == 1
    raw = '{"blood": {"weights": {"expiry": 0, "distance": 1}}}'
    with override_settings(MATCHING_SCORING=parse_scoring_config(raw)):
        assert ranked(blood_item(), 3, soon_far, late_near)[0].candidate.hospital.pk == 2


# Ranking.


def test_equal_distance_earlier_expiry_ranks_first():
    late = candidate(pk=1, distance_km=10, expires_in=40, donor_rank=0)
    soon = candidate(pk=2, distance_km=10, expires_in=3, donor_rank=0)
    assert [s.candidate.hospital.pk for s in ranked(blood_item(), 3, late, soon)] == [2, 1]


def test_more_stock_ranks_first_under_the_most_stock_override():
    near = candidate(pk=1, distance_km=5, available=2)
    deep = candidate(pk=2, distance_km=30, available=8)

    assert ranked(bed_item(), 4, near, deep)[0].candidate.hospital.pk == 1  # nearest-first default

    with override_settings(MATCHING_SCORING=parse_scoring_config('{"bed": {"strategy": "mostStock"}}')):
        assert isinstance(strategy_for(ResourceType.BED), MostStockFirst)
        assert ranked(bed_item(), 4, near, deep)[0].candidate.hospital.pk == 2


def test_ties_are_ordered_by_hospital_id_whatever_the_input_order():
    trio = [candidate(pk=pk, distance_km=10, expires_in=20, donor_rank=0) for pk in (3, 1, 2)]
    orders = {
        tuple(s.candidate.hospital.pk for s in ranked(blood_item(), 3, *permutation))
        for permutation in itertools.permutations(trio)
    }
    assert orders == {(1, 2, 3)}


def test_rank_numbers_the_candidates_from_one_in_order():
    near = candidate(pk=1, distance_km=2)
    far = candidate(pk=2, distance_km=30)

    result = ranked(bed_item(), 3, far, near)

    assert [(s.rank, s.candidate.hospital.pk) for s in result] == [(1, 1), (2, 2)]


# Validation: each case refuses the setting with ImproperlyConfigured.


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("{not json", "not valid JSON"),
        ("[]", "must be a JSON object"),
        ('{"parking": {}}', "unknown resource type 'parking'"),
        ('{"blood": []}', "'strategy' and 'weights' only"),
        ('{"blood": {"colour": "red"}}', "'strategy' and 'weights' only"),
        ('{"blood": {"strategy": "nope"}}', "unknown strategy 'nope'"),
        ('{"blood": {"strategy": ["x"]}}', "unknown strategy"),
        ('{"blood": {"weights": []}}', "'weights' must be an object"),
        ('{"bed": {"weights": {"expiry": 0.5}}}', "does not use the factor 'expiry'"),
        ('{"bed": {"weights": {"compatibility": 0.1}}}', "does not use the factor 'compatibility'"),
        ('{"blood": {"weights": {"expiry": -0.1}}}', "must be a number"),
        ('{"blood": {"weights": {"expiry": "high"}}}', "must be a number"),
        ('{"blood": {"weights": {"expiry": true}}}', "must be a number"),
        ('{"blood": {"weights": {"expiry": NaN}}}', "must be a number"),
        (
            '{"blood": {"weights": {"expiry": 0, "compatibility": 0, "distance": 0, "quantity": 0}}}',
            "all weights are zero",
        ),
        ('{"bed": {"weights": {"distance": 0, "quantity": 0}}}', "all weights are zero"),
    ],
)
def test_every_bad_setting_is_refused_with_a_clear_message(raw, message):
    with pytest.raises(ImproperlyConfigured, match=f"MATCHING_SCORING.*{message}"):
        parse_scoring_config(raw)


def test_a_strategy_refuses_bad_weights_built_in_code():
    with pytest.raises(ImproperlyConfigured, match="all weights are zero"):
        NearestFirst({"distance": 0, "quantity": 0})
    with pytest.raises(ImproperlyConfigured, match="must be a number"):
        EarliestExpiryFirst({"expiry": -1})
