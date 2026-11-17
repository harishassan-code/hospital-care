# Construction Plan: Ranked results with explanation

**Spec:** [docs/aidlc/inception/2026-11-17-ranked-results-with-explanation.md](../inception/2026-11-17-ranked-results-with-explanation.md)
**Date:** 2026-11-17
**Author:** Krrishna

## Design

- **Scoring module.** `backend/apps/matching/scoring.py` gains:
  - `FACTOR_LABELS`: the human label of each factor ("Distance", "Expiry", "Stock", "Blood group match").
  - A `label` on each strategy class ("Earliest expiry first", "Nearest first", "Most stock first").
  - `detail` on `FactorScore`, filled by one detail function per factor (`DETAILS`), which takes the same arguments as
    the factor functions and returns a short string. Distance says "4.2 km, about 6 min" or "distance unknown". Expiry
    says "expires in 3 days" or "expires within a day". Stock says "5 available, 3 needed". Compatibility says
    "identical group" or "compatible substitute, rank 2", and "no compatible units" when unknown.
  - `strategy` (the name) on `Score`, and `rank` (1-based) on `ScoredCandidate`. `rank()` sets the positions.
  - Factor points are rounded to one decimal when they are built, and the total is the sum of those points, so the
    numbers a coordinator reads add up exactly.
- **Endpoint.** `CandidateItemSerializer` in `backend/apps/emergencies/serializers.py` calls `rank(found)` and adds
  `strategy: {name, label}` to each item. `CandidateSerializer` adds `rank`, `score` (`total`, `strategy`, `factors` with
  `name`, `label`, `value`, `weight`, `points`, `detail`) and `recommended` (rank 1 with a total above 0).
  `CaseCandidatesView` and `candidates_for_case` do not change, so the queries do not change.
- **Settings.** No change. `MATCHING_SCORING` and `MATCHING_MAX_DISTANCE_KM` still decide the order.
- **Frontend.** `frontend/src/api/emergencies.ts` gets the new types (`ScoreFactor`, `Score`, and the new fields on
  `Candidate` and `CandidateItem`). `EmergencyCasePage.tsx` renders the server's order. The top row carries a
  "Recommended" badge and an emphasised border. Each row shows rank, hospital, score out of 100, available and
  covers or partial, and distance with travel time. "Why this score?" is a native `<details>` that lists each factor
  with its detail and points, then the total. The fixtures and `sampleCandidates` carry the new fields.
- **Not changed.** `candidates.py`, the blood app, the feed, the other staff pages and the settings.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Docs: inception, construction plan, the #39 follow-up | `docs/aidlc/inception/2026-11-17-ranked-results-with-explanation.md`, `docs/aidlc/construction/2026-11-17-ranked-results-with-explanation.md`, `docs/aidlc/operations/2026-11-11-distance-and-travel-time.md` | none |
| 2 | Scoring: labels, details, `rank` positions, rounded points | `backend/apps/matching/scoring.py`, `backend/apps/matching/candidates.py` (docstring only) | `backend/apps/matching/tests/test_scoring.py` |
| 3 | API: rank order, score, `recommended`, strategy on the item | `backend/apps/emergencies/serializers.py`, `backend/apps/emergencies/views.py` (docstring only) | `backend/apps/emergencies/tests/test_candidates_api.py` |
| 4 | Query budget with ranking and serialisation included | none | `backend/apps/matching/tests/test_candidates_performance.py` |
| 5 | Frontend types, fixtures, panel, disclosure, styles | `frontend/src/api/emergencies.ts`, `frontend/src/test/fixtures/emergencies.ts`, `frontend/src/pages/staff/EmergencyCasePage.tsx`, `frontend/src/features/emergencies/Emergencies.module.css` | `frontend/src/pages/staff/EmergencyCasePage.test.tsx` |
| 6 | API doc: the new fields and the ordering | `docs/architecture/api.md` | none |

## Sequencing

Unit 1 first, as the spec requires. Units 2 and 3 next, since the API needs the scoring additions. Unit 4 with unit 3.
Unit 5 after the API shape is fixed, and unit 6 last.

## Test plan

Backend:

- Factor details: distance with and without a distance; expiry with days, under a day and unknown; stock; compatibility at
  rank 0, at a substitute rank and unknown.
- Points: each factor's points are one decimal, and the total equals the sum of the points.
- Ranks: positions are 1 to n in the order `rank` returns.
- API, blood: at equal distance, the earlier expiry comes first, rank 1 is recommended, rank 2 is not.
- API, beds: the nearest comes first although it was created second.
- API, recommended: only rank 1, and not when its total is 0 (distance weight 1, stock weight 0, a hospital beyond the
  maximum distance).
- API, override: `MATCHING_SCORING` with `mostStock` for beds changes the order through the endpoint.
- API, breakdown: each candidate's points add up to its total within 0.05, and each item names its strategy.
- Query budget: `candidates_for_case` and the serialisation together stay within the #38 budget of 10 queries.

Frontend:

- Rows render in server order, with rank and score.
- The top row is labelled "Recommended", and the others are not.
- The disclosure lists each factor's label, detail and points, then the total.
- Distance and travel time are shown, and "Distance unknown" when the distance is null.
- The existing tests for the marker, expiry, empty state and the no-request case still pass.

Verification, from the task: Postgres and SQLite pytest, ruff check and format, `makemigrations --check`, `manage.py check`,
frontend lint, test and build, and a grep for the writing rules.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified.** Postgres: 906 passed. SQLite: 903 passed, 2 skipped, and one failure that is not this story's
  (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, the known SQLite issue). Ruff check and format
  are clean, `makemigrations --check` detects no changes, and `manage.py check` reports no issues. Frontend: lint clean,
  375 tests in 38 files passing, production build passing.
- **Changes from the spec's wording.**
  - The stock detail reads "5 available, 3 needed". The spec's example, "4 of 2 needed", reads as if the available
    count were a fraction of the need.
  - The expiry detail rounds to the nearest whole day, so a unit due in 9 days still reads 9 when it is ranked a few
    milliseconds later. Flooring it read 8.
  - Factor points are rounded to one decimal in `scoring.py`, and the total is the sum of those points. #40 rounded only
    the total, from unrounded points, so shown points could differ from the total by 0.1 or more. The #40 test that
    compared points to their unrounded value now allows 0.05, which is the rounding.
- **Unchanged.** The candidate lists, the sources list's distance text ("4.2 km · ~6 min", "Distance unknown") and the
  empty state are as before. The query budget is unchanged at 10 for the whole search, now including the ranking and the
  serialising, and `test_candidates_performance.py` asserts it.
- **Not done here.** Nothing is reserved or requested from the recommended hospital (#45). Multi-resource matching is
  #42. The inception doc's sign-off is pending the Product Owner.
