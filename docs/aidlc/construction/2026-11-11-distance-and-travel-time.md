# Construction Plan: Distance and estimated travel time

**Spec:** [docs/aidlc/inception/2026-11-11-distance-and-travel-time.md](../inception/2026-11-11-distance-and-travel-time.md)
**Date:** 2026-11-11

## Units of work

One unit — the whole spec fits in a single reviewable PR.

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Add a `distance` module to `apps/matching` with a Haversine distance function and a travel-time estimate function; unit tests for both | `backend/apps/matching/distance.py` (new), `backend/apps/matching/tests/test_distance.py` (new) | pytest: zero-distance case, known city-pair sanity check, travel-time conversion at default and custom speed |

## Sequencing

No dependencies — `Hospital.latitude`/`longitude` already exist, and this unit doesn't touch any
other app or model.

## Test plan

- `cd backend && pytest apps/matching/` — new tests pass.
- `cd backend && ruff check . && ruff format --check .` — matches existing CI lint step.
- No migrations, no frontend changes, so `npm test`/`npm run build` are unaffected by this unit.

## Review

This unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before
merge — that approval is the Construction gate.
