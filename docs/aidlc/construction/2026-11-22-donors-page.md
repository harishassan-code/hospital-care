# Construction Plan: Donors page

**Spec:** [docs/aidlc/inception/2026-11-22-donors-page.md](../inception/2026-11-22-donors-page.md)
**Bolt:** [B11](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | API client + nav item (`donors`, blood bank and admin; endpoints keep `blood`) | `frontend/src/api/donors.ts`, `roles.ts`, `permissions.py` | roles parity test |
| 2 | Donors page: list, search, register, screening, appointments | `src/pages/staff/DonorsPage.tsx`, `src/test/mockApi.ts` | `Sprint8Pages.test.tsx`: register, defer, book, cancel |

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
