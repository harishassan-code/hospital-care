# QA & testing artefacts

| Document | Purpose |
|---|---|
| [qa-test-case-catalog.md](qa-test-case-catalog.md) | Full test cases from Muhammad Hassaan’s QA sheets (PR #70), **adapted to the current Northgate frontend + Django API** |
| [authentication-test-report.md](authentication-test-report.md) | Execution report: results, traceability, screenshots, demo script |
| [source/login-positive-test-cases.md](source/login-positive-test-cases.md) | Original positive login sheet (CityCare, Oct 2026) |
| [source/carelink-negative-test-cases.md](source/carelink-negative-test-cases.md) | Original CareLink negative sheet (login + landing) |
| [results/](results/) | Latest `npm test` / `pytest` output snapshots |

**Automated QA-sheet tests (Vitest):**

- `frontend/src/qa/login.qa.test.tsx` — TC-* and LOGIN-N*
- `frontend/src/qa/staff-workspace.qa.test.tsx` — LAND-N* (staff workspace at `/staff`)
- `frontend/src/qa/landing-public.qa.test.tsx` — PUB-* / public home (TC-01 entry)

Run: `cd frontend && npm test`
