# Construction Plan: Security and performance hardening

**Spec:** [docs/aidlc/inception/2026-11-22-security-performance.md](../inception/2026-11-22-security-performance.md)
**Bolt:** [B13](../bolts/B13-security-performance.md)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Deploy settings (SSL redirect, HSTS) + check test | `backend/config/settings.py`, `apps/core/tests/test_security.py` | `check --deploy --fail-level WARNING` exits 0 with production env |
| 2 | Permission coverage test + review notes | `apps/core/tests/test_security.py`, `docs/testing/security-review.md` | every API view names a role-based permission or is on a commented allow-list |
| 3 | `seed_demo --hospitals N` + load test script + report | `seed_demo.py`, `scripts/load_test_search.py`, `docs/testing/performance-report.md` | run locally; rerun on staging for the final report |

## Sequencing

Settings and the check test first; then the permission test and review; then the scaled seed and the load test.

## Test plan

All CI checks green: backend `ruff check`, `ruff format --check`, `makemigrations --check`, `pytest`; frontend
`npm run lint`, `npm test`, `npm run build`; `scripts/check_deploy_config.py` and `scripts/aidlc_board.py --check`.
Then UAT checklist rows 28 and 29 (`docs/testing/uat-checklist.md`) on staging.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before
merge — that approval is the Construction gate.
