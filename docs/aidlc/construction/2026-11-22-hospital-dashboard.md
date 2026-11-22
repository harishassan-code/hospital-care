# Construction Plan: Hospital dashboard: requests, transfers and live refresh

**Spec:** [docs/aidlc/inception/2026-11-22-hospital-dashboard.md](../inception/2026-11-22-hospital-dashboard.md)
**Bolt:** [B08](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | 60 s refresh of staff data in StaffProvider (paused when hidden) | `frontend/src/features/staff/StaffProvider.tsx` | existing Overview tests still pass |
| 2 | Open emergencies + pending transfers panels | `src/features/overview/RequestsAndTransfers.tsx`, `src/pages/staff/OverviewPage.tsx` | `Sprint8Pages.test.tsx`: panels shown |

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
