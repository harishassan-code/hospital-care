# Inception Spec: Ranked results with explanation

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** #41 Ranked results with explanation (Epic E4, Sprint 6; builds on
[#38 Find candidate hospitals](2026-11-17-find-candidate-hospitals.md),
[#40 Configurable scoring model](2026-11-17-configurable-scoring-model.md) and
[#39 Distance and travel time](2026-11-11-distance-and-travel-time.md), whose display half this story completes)

## Problem

The candidate search (#38) lists the hospitals that can supply a case's shortfall. #40 scores them by configurable
rules and provides `rank`, but nothing shows the scores yet. A coordinator sees a list in a plain order (covering
first, then nearest) with no recommendation, and no reason for the order. Distance and estimated travel time (#39)
are computed by the API but never shown, so the nearer-source preference cannot be seen or trusted.

A coordinator should be able to see why a candidate is ranked first, so that they can trust the recommendation or
overrule it knowingly.

## User stories

- As a coordinator, I want to see why a candidate is ranked first so that I can trust the recommendation. (#41)
- As a coordinator, I want to see the distance and travel time of each source, so that nearer sources are visibly
  preferred. (#39, display half)

## Acceptance criteria

- [ ] Each result shows its score breakdown: each factor's label, its detail in plain words, and its points, with the
      points adding up to the total.
- [ ] The results are sorted by score, on the server, and the screen shows them in that order without re-sorting.
- [ ] The top result is a clear recommendation: a labelled "Recommended" badge and emphasis, not colour alone.
- [ ] Each result shows the hospital, its score out of 100, how many it has and whether that covers the shortfall, and
      its distance and estimated travel time, or "distance unknown" when the distance is not known.
- [ ] The breakdown is a native disclosure ("Why this score?"), so it needs no script state and is keyboard and screen
      reader friendly.
- [ ] The empty state ("No other hospital has this right now") is kept.
- [ ] The query count of the candidates request stays the same as #38's. Scoring is pure Python over rows already
      fetched.

## Design decisions

- **Extend the endpoint, do not add one.** `GET /api/emergencies/<ref>/candidates/` keeps its shape and gains fields.
  Its items and candidates keep every field they had.
- **Ranking is `rank` from #40.** Each item's candidates come back in the order `scoring.rank` gives, using
  `strategy_for(resource_type)`. The server sorts; the client keeps the order it receives.
- **Each candidate carries its position and its score.** `rank` is 1-based. `score` holds `total` (0 to 100, one
  decimal), `strategy` (the strategy's name) and `factors`. Each factor has `name`, `label` (for example "Distance",
  "Expiry", "Stock", "Blood group match"), `value` (0 to 1, two decimals), `weight` (its share of the total weight, 0
  to 1, two decimals), `points` (one decimal) and `detail` (a short reason, such as "4.2 km, about 6 min" or "expires in
  3 days").
- **Points are rounded before they are added.** Each factor's points are rounded to one decimal in `scoring.py`, and
  the total is the sum of those rounded points. So the points a coordinator reads add up exactly to the total shown,
  with no rounding gap. Candidates whose totals are equal after rounding are ordered by distance, then hospital id.
- **Recommended.** `recommended` is `true` only on rank 1, and only when its total is above 0. A candidate that scores
  0 (for example, no distance and a strategy that weighs only distance) is not recommended, because nothing supports
  it.
- **Each item names its strategy.** `strategy` is `{name, label}`, for example `{"name": "earliestExpiry", "label":
  "Earliest expiry first"}`, so the screen can say how the list is ordered.
- **Ordering stays as #40 defined it.** The sort key is total score, then distance (no distance last), then hospital
  id. Covering is not a sort key. Stock depth counts only through the quantity factor, so a candidate that covers less
  can rank above one that covers more when its distance and expiry are much better. The screen shows the stock
  numbers, so this can be seen.
- **Distance and travel time are shown.** The row shows "4.2 km · ~6 min", using the fields #39 already puts on the
  candidate. When the distance is unknown, it shows "distance unknown".
- **Frontend.** The "Sources in the network" panel on the case page is the only screen that changes. The disclosure is
  a native `<details>` element.

## Non-goals

- Changing the scoring rules, weights or defaults. Those are #40.
- Sorting on the client, or any ranking rule that the server does not produce.
- A new endpoint, a new setting or a stored score. Nothing is written to the database.
- Reserving or requesting stock from the recommended hospital. **#45.**
- Multi-resource matching across several needs at once. **#42.**
- Showing scores for the feed or for any screen other than the case page.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Recommended only when the score is above 0.** Proposed: a score of 0 means the strategy found nothing to support
   the candidate, so no badge. The alternative is to recommend rank 1 whatever its score, which would call a zero-score
   candidate "recommended".
2. **Covering is not a sort key (carried from #40).** Proposed: keep it, and show the stock count next to the score, so
   a coordinator who wants covering first can see that a partial candidate ranked above a covering one and why. The
   alternative is to put covering first again, which would make the score stop deciding the order.
3. **The detail wording.** Proposed: short plain phrases, one per factor, that a coordinator can read in a second. For
   stock the detail reads "5 available, 3 needed", which states the numbers without implying a comparison the score
   does not make.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
