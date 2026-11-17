# Inception Spec: Configurable scoring model

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** #40 Configurable scoring model (Epic E4, Sprint 6; builds on
[#38 Find candidate hospitals](2026-11-17-find-candidate-hospitals.md),
[#37 Blood compatibility matching](2026-11-17-blood-compatibility-matching.md) and
[#39 Distance and travel time](2026-11-11-distance-and-travel-time.md))

## Problem

The candidate search (#38) lists the hospitals that can supply a case's shortfall, in a plain order: covering first,
then nearest, then hospital id. That order ignores expiry, stock depth and blood compatibility, and it cannot be
changed without editing code. Coordinators need the candidates scored by rules they can explain, so that two
coordinators facing the same shortfall pick from the same order, and so that a hospital can change the rules without a
release.

This story scores and orders the candidates. It does not show the scores or their breakdown (#41), and it does not
change the API or the screen.

## User stories

- As a coordinator, I want candidates scored by configurable rules (distance, expiry, quantity) so that selection is
  consistent. (#40)

## Acceptance criteria

- [ ] Scoring is implemented as interchangeable strategy classes. A resource type's strategy can be swapped without
      changing the search or the score.
- [ ] Earliest-expiry-first is the default blood strategy.
- [ ] Nearest-first is the default for beds, equipment and operating rooms.
- [ ] Weights, and the strategy per resource type, are configurable through the environment without code changes. A
      bad setting stops the server at startup with a message that names the problem.

## Design decisions

- **Fixed scale per factor.** Each factor is a value from 0 to 1 on a fixed scale, not a min-max over the candidate
  set. A value of 0.8 means the same thing in every search, which is what makes a score explainable.
  - Distance: `1 - min(km / MAX_KM, 1)`. `MAX_KM` is `MATCHING_MAX_DISTANCE_KM` (default 50). No distance: 0.
  - Expiry (blood): `1 - min(days_left / horizon, 1)`. The horizon is the component's shelf life from the blood app
    (`SHELF_LIFE_DAYS`: red cells 42 days, platelets 5, plasma and cryo 365), so a platelet unit four days from expiry
    scores lower than a red cell unit four days from expiry. No expiry: 0.
  - Quantity: `min(available / needed, 1)`. Covering is not a separate rule: a candidate that covers the shortfall
    scores 1 on this factor.
  - Compatibility (blood): `1 - rank / 8`. Rank 0 (the identical group) scores 1, and the worst rank scores 0.125, so
    a compatible substitute is never worth nothing. No rank: 0.
- **Strategies are weighted sums.** A strategy names the factors it uses and their default weights. The score is the
  weighted average of its factor values on a 0 to 100 scale: each factor contributes `value x weight x 100 / total
  weight`, and the total is rounded to one decimal. Weights need not sum to 1, because the total weight is the divisor.
- **Strategies.**

  | Strategy | Name | Default for | Factors and default weights |
  |---|---|---|---|
  | `EarliestExpiryFirst` | `earliestExpiry` | blood | expiry 0.5, compatibility 0.2, distance 0.2, quantity 0.1 |
  | `NearestFirst` | `nearest` | bed, equipment, operatingRoom | distance 0.7, quantity 0.3 |
  | `MostStockFirst` | `mostStock` | none (an override) | quantity 0.7, distance 0.3 |

  `MostStockFirst` is there to prove the strategies are interchangeable: the same search with another strategy gives
  another order, and nothing else changes.
- **Ranking.** Candidates are sorted by total score (highest first), then by distance (nearest first, no distance
  last), then by hospital id. The order is deterministic on ties. Covering is not a separate sort key, so a candidate
  that covers less can rank above one that covers more when its distance and expiry are much better. The quantity
  factor is the only place stock depth counts.
- **Configuration without code changes.** Two settings, read from the environment in `config/settings.py`:
  - `MATCHING_SCORING`: a JSON object keyed by resource type. Each entry may set `strategy` and `weights`. Anything not
    mentioned keeps its default, and weights not mentioned keep the strategy's defaults:

    ```json
    {"blood": {"strategy": "earliestExpiry", "weights": {"expiry": 0.6, "distance": 0.4}}, "bed": {"strategy": "mostStock"}}
    ```

    In that example blood keeps `earliestExpiry` with expiry 0.6, distance 0.4, and its default compatibility 0.2 and
    quantity 0.1. Beds switch to `mostStock` with its default weights.
  - `MATCHING_MAX_DISTANCE_KM`: a whole number of 1 or more, read with `positive_int_env` (default 50).
- **Validation at startup.** `parse_scoring_config` in `apps/matching/scoring.py` raises `ImproperlyConfigured` for: bad
  JSON, a value that is not an object, an unknown resource type, an unknown strategy, an unknown key in an entry, a
  weight for a factor the strategy does not use, a weight that is negative, not a number, not finite, or a boolean, and
  weights that are all zero. Because the settings module runs it, `manage.py check` and the server both refuse to start.
- **No API or UI change.** The candidates endpoint (#38) keeps its response. Story #41 exposes the score and the
  factor breakdown, and the frontend shows them then.

## Non-goals

- Showing scores, breakdowns or the ranked list in the API or the screen. **#41.**
- Min-max or percentile normalisation across the candidate set. Rejected above, because a score must mean the same in
  every search.
- Per-hospital or per-coordinator weights. The configuration is per deployment.
- Learned or adaptive weights.
- Reserving or requesting stock from the ranked hospitals. **#45.**

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Expiry horizon per component.** Proposed: the horizon is the component's shelf life, so the same days-left scores
   differently for platelets (5 days) and plasma (365 days). The alternative is one horizon for all blood, which is
   simpler, but it would call a platelet unit with four days left "fresh".
2. **Covering is not a sort key.** Proposed: the quantity factor carries stock depth, and covering is not a separate
   rule, so a far, fresh, partial candidate can outrank a near, short-dated, covering one. The alternative is to keep
   covering first, as #38 does, and score within each group. That would mean the score does not decide the order.
3. **Negative and zero weights.** Proposed: negative weights are refused, and a weight of 0 switches a factor off
   while keeping it in the breakdown. The alternative is to refuse 0 as well, which would hide a deliberate choice.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
