---
id: B12
title: End-to-end MVP scenario test
issues: 57
points: 5
priority: highest
sprint: 9
depends_on: B03
owner: harishassan-code
status: Done
---

# B12 · End-to-end MVP scenario test

**Goal:** The MVP acceptance scenario runs automatically in CI, in a real browser against real servers: request → match → reserve → transfer → receipt across the three seeded hospitals.

## Stories and acceptance criteria

[#57](https://github.com/harishassan-code/hospital-care/issues/57): Automate the MVP acceptance scenario.

- [x] Scenario runs in CI: the `e2e` job, green on three consecutive runs of one commit ([1](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/1), [2](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/2), [3](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/3))
- [x] Covers every MVP acceptance criterion in the proposal (§23): mapped step by step in
      [mvp-scenario.md](../../testing/mvp-scenario.md#what-23-each-step-covers); 2 and 4 partly, with the rest in unit tests

## Build on

- `seed_demo` creates three hospitals and one login per role (README "Signing in").
- The shortfall in the demo data is real: CityCare General has no free ICU bed while Seaview has two, and
  O− red cells are critically low. The scenario can be built on that.
- Playwright is not in the repo yet: add it as a small `e2e/` project and a CI job that starts Postgres, the API
  (`migrate`, `seed_demo`, `runserver`) and `vite preview`.

## Scope

- **In:** Playwright project, scenario test, CI job.
- **Out:** Load testing (B13).

## Open questions for Inception

- Run on every push, or only on PRs to `main` (it's slower)?

## Exit checklist

- [x] Inception spec [`docs/aidlc/inception/2026-11-18-e2e-mvp-scenario.md`](../inception/2026-11-18-e2e-mvp-scenario.md) approved (sign-off line filled in)
- [x] Construction plan [`docs/aidlc/construction/2026-11-18-e2e-mvp-scenario.md`](../construction/2026-11-18-e2e-mvp-scenario.md) written
- [x] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met (last change: #124)
- [ ] Operations notes `docs/aidlc/operations/<date>-e2e-mvp-scenario.md` written after it's live on staging
- [x] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed (#57)
