# Construction Plan: City command centre dashboard

**Spec:** [docs/aidlc/inception/2026-11-22-city-command-centre.md](../inception/2026-11-22-city-command-centre.md)
**Bolt:** [B09](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Aggregate endpoint with fixed query count | `backend/apps/core/command_centre.py`, `config/urls.py`, access table | `apps/core/tests/test_command_centre.py`: admin only, aggregates, shortages, query count flat |
| 2 | Command centre page | `frontend/src/api/commandCentre.ts`, `src/pages/staff/CommandCentrePage.tsx` | `Sprint8Pages.test.tsx`: totals, shortages, rows; doctor denied |

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
