"""Multi-resource matching (story #42): which single hospital can supply the most of a case's short needs.

Pure Python over `candidates_for_case` (#38) and the scores from `scoring.rank` (#41). It adds no query.
Needs that draw on the same stock at one hospital (two O- red-cell lines, two ICU bed lines) share that
hospital's count, judged in item order, so a hospital is not credited twice with the same units.

Known limit: blood candidates are grouped per need, so two needs with different groups can both count the
same donor unit at a hospital. Allocation (#45) resolves that exactly; it is not solved here.
"""

from dataclasses import dataclass, replace

from apps.emergencies.availability import _stock_key
from apps.emergencies.models import RequestItem
from apps.hospitals.models import Hospital

from .candidates import Candidate, ItemCandidates
from .scoring import rank


@dataclass(frozen=True)
class NeedMatch:
    item: RequestItem
    shortfall: int  # what the case still needs of this requirement
    # What the hospital has for it, after the needs before it on the same stock have claimed theirs.
    available: int

    @property
    def covered(self) -> bool:
        return self.available >= self.shortfall

    @property
    def missing(self) -> int:
        return max(0, self.shortfall - self.available)


@dataclass(frozen=True)
class HospitalMatch:
    hospital: Hospital
    total_needs: int
    covered: tuple[NeedMatch, ...]
    unmet: tuple[NeedMatch, ...]  # every need not fully covered: partial ones, and those it has none of
    score: float  # the mean of its #41 scores over the needs it has candidates for, to one decimal
    distance_km: float | None
    travel_minutes: int | None
    rank: int = 0  # 1-based position in the list; 0 until match_hospitals() sets it

    @property
    def complete(self) -> bool:
        return not self.unmet

    @property
    def partial(self) -> tuple[NeedMatch, ...]:
        """The unmet needs the hospital has some of, but not enough."""
        return tuple(match for match in self.unmet if match.available > 0)


def match_hospitals(item_candidates: list[ItemCandidates]) -> list[HospitalMatch]:
    """One HospitalMatch per hospital that is a candidate for at least one short need, best first.

    Complete ones come first, then the most needs covered, then the highest score, then the nearest (no
    distance last), then the hospital id. Empty when nothing is short. Deterministic on ties.
    """
    scored = [{found.candidate.hospital.pk: found for found in rank(entry)} for entry in item_candidates]
    seen: dict[int, Candidate] = {}
    for by_hospital in scored:
        for pk, found in by_hospital.items():
            seen.setdefault(pk, found.candidate)
    matches = [_judge(candidate, item_candidates, scored) for candidate in seen.values()]
    matches.sort(key=_order)
    return [replace(match, rank=position) for position, match in enumerate(matches, 1)]


def _judge(candidate: Candidate, item_candidates: list[ItemCandidates], scored: list[dict]) -> HospitalMatch:
    """What one hospital covers. Each need is judged against the hospital's stock for it, less what the needs
    before it on the same stock have taken."""
    pk = candidate.hospital.pk
    remaining: dict[tuple, int] = {}
    covered, unmet, totals = [], [], []
    for entry, by_hospital in zip(item_candidates, scored, strict=True):
        found = by_hospital.get(pk)
        key = _stock_key(entry.item)
        if key not in remaining:
            remaining[key] = found.candidate.available if found else 0
        available = remaining[key]
        remaining[key] = max(0, available - entry.shortfall)
        match = NeedMatch(entry.item, entry.shortfall, available)
        (covered if match.covered else unmet).append(match)
        if found:
            totals.append(found.score.total)
    return HospitalMatch(
        hospital=candidate.hospital,
        total_needs=len(item_candidates),
        covered=tuple(covered),
        unmet=tuple(unmet),
        score=round(sum(totals) / len(totals), 1),
        distance_km=candidate.distance_km,
        travel_minutes=candidate.travel_minutes,
    )


def _order(match: HospitalMatch) -> tuple:
    return (
        not match.complete,
        -len(match.covered),
        -match.score,
        match.distance_km is None,
        match.distance_km or 0.0,
        match.hospital.pk,
    )
