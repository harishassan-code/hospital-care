# Construction Plan: Ambulance dispatch and trip tracking

**Spec:** [docs/aidlc/inception/2026-11-22-ambulance-dispatch.md](../inception/2026-11-22-ambulance-dispatch.md)
**Bolt:** [B05](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Trip model and lifecycle | `apps/ambulances/models.py` | trip states via StateMachine |
| 2 | Dispatch / en route / arrived services and API; end trip on receipt or cancel | `apps/ambulances/services.py`, `views.py`, `urls.py`, `apps/transfers/services.py` (`_move` calls `end_trip_for`), `apps/transfers/serializers.py` + `models.py` (`trip` on each transfer) | available-only (409), other hospital's ambulance refused, en route moves transfer to in transit, receipt completes trip and frees ambulance, cancel cancels trip |
| 3 | Trip controls on the Transfers page | `frontend/src/features/transfers/TripControls.tsx`, `TransfersPage.tsx`, `src/api/transfers.ts` | covered by the e2e scenario (B12) |

## Sequencing

Backend before frontend within the bolt. Sprint 8 order across bolts: B06 → B07, B04 → B05, B10, B11, B09, B08,
B13, B12 (the end-to-end scenario uses everything before it).

## Test plan

All CI checks green: backend `ruff check`, `ruff format --check`, `makemigrations --check`, `pytest`; frontend
`npm run lint`, `npm test`, `npm run build`; `scripts/check_deploy_config.py` and `scripts/aidlc_board.py --check`.
Then the UAT checklist row for this story (`docs/testing/uat-checklist.md`) on staging.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before
merge — that approval is the Construction gate.
