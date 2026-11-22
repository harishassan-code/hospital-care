# Construction Plan: Audit search and export

**Spec:** [docs/aidlc/inception/2026-11-22-audit-search-export.md](../inception/2026-11-22-audit-search-export.md)
**Bolt:** [B10](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Filtered, paginated list + streamed CSV export (export audit-logged) | `backend/apps/audit/views.py`, `urls.py`, access table | `apps/audit/tests/test_search_export.py`; no write methods |
| 2 | Audit page | `frontend/src/api/audit.ts`, `src/pages/staff/AuditPage.tsx` | `Sprint8Pages.test.tsx`: prefix filter, export link carries filters |

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
