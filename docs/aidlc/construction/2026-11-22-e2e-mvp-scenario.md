# Construction Plan: End-to-end MVP scenario test and UAT checklist

**Spec:** [docs/aidlc/inception/2026-11-22-e2e-mvp-scenario.md](../inception/2026-11-22-e2e-mvp-scenario.md)
**Bolt:** [B12](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Partner-hospital logins in seed data | `backend/apps/core/management/commands/seed_demo.py` | seed runs |
| 2 | Playwright project + scenario | `e2e/package.json`, `e2e/playwright.config.ts`, `e2e/tests/mvp-scenario.spec.ts` | the scenario itself |
| 3 | CI job on PRs and manual dispatch | `.github/workflows/ci.yml` | green on the PR |
| 4 | UAT checklist for the Product Owner | `docs/testing/uat-checklist.md` | PO signs it |

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
