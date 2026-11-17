# Operations Notes: Distance and estimated travel time

**Construction plan:** [docs/aidlc/construction/2026-11-11-distance-and-travel-time.md](../construction/2026-11-11-distance-and-travel-time.md)
**Merged:** 2026-11-11, [PR #91](https://github.com/harishassan-code/hospital-care/pull/91)
**Deployed to staging:** N/A — backend utility with no endpoint yet; nothing to deploy or observe in staging until it's wired into the matching engine.

## Outcome

- [x] Haversine straight-line distance in km between two hospitals' coordinates — met. See
      `backend/apps/matching/distance.py:haversine_km` / `hospital_distance`.
- [x] Simulated travel-time estimate in minutes from a configurable average city speed — met.
      `estimated_travel_minutes`, default 40 km/h as agreed in the Inception spec.
- [x] Exposed as a reusable utility for the matching engine — met. No endpoint/UI yet, as scoped
      (non-goal in the Inception spec).
- [x] Unit tests: zero distance, known reference value, travel-time conversion — met, 9 tests in
      `backend/apps/matching/tests/test_distance.py`, all passing in CI.

## Monitoring notes

No runtime behaviour to monitor yet — this unit only added a pure-function utility and its tests,
with no new endpoint, migration, or UI surface. CI (`ruff check`, `ruff format --check`, `pytest`)
was green on merge.

## Follow-ups

- Wire `hospital_distance`/`estimated_travel_minutes` into the scoring model once
  [#40 Configurable scoring model](https://github.com/harishassan-code/hospital-care/issues/40) is
  built — that PR should go through its own AIDLC cycle, with its Inception spec referencing this
  utility as already available.
- [#41 Ranked results with explanation](https://github.com/harishassan-code/hospital-care/issues/41)
  now shows the distance and estimated travel time of each source on the case page, with "distance unknown" when the
  distance is not known (see [the construction plan](../construction/2026-11-17-ranked-results-with-explanation.md)).
  This completes the display half of #39.
- [#42 Multi-resource matching](https://github.com/harishassan-code/hospital-care/issues/42) is the remaining
  consumer; no action needed on this unit until it's scheduled.

This closes the Inception → Construction → Operations loop for #39, demonstrating the full AIDLC
cycle end to end.
