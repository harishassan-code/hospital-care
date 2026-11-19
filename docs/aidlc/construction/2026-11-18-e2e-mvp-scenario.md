# Construction Plan: End-to-end MVP scenario test

**Spec:** [docs/aidlc/inception/2026-11-18-e2e-mvp-scenario.md](../inception/2026-11-18-e2e-mvp-scenario.md)
**Bolt:** [B12](../bolts/B12-e2e-mvp-scenario.md) · [#57](https://github.com/harishassan-code/hospital-care/issues/57)
**Date:** 2026-11-18

## Design

- **One browser test, twelve steps.** `e2e/tests/mvp-scenario.spec.ts` is one serial test. Each step is a
  `test.step` titled with its §23 number, and the steps share the case reference and transfer id they create.
- **One browser context per seeded login.** The admin, nurse, blood bank and doctor sign in once each through
  `/login`, as a user would. Cookies stay per role, so no step signs another person out.
- **Every number is read from the page.** The local stock `L` is read from "Available here", the transfer quantity
  from its input, and the candidates from the sources list. The seed preconditions are asserted with messages that name
  the precondition. Nothing is skipped and nothing is retried (`retries: 0`).
- **Waiting is Playwright's.** `expect` auto-waits on locators and URLs. No fixed sleeps. The `expect` timeout is raised
  to 15 seconds so a slow CI runner does not fail a correct page.
- **Selectors.** Roles, visible labels and the page sections' existing ids (`#case`, `#sources`, `#reservations`,
  `#history`, `#moves`, `#case-transfers`, `#outcome`). A `data-testid` is added only if a step cannot be found that way
  (unit 4, not expected).
- **Servers are started outside Playwright.** No `webServer` block (per the approved spec). CI and the local commands in
  the testing doc start `runserver localhost:8000` on a fresh database and `vite preview` on port 5173.
- **Seed change.** `seed_demo` sets CityCare's usable O− red-cell count to exactly one, after the random draws, so the
  random stream and every other demo number keep their values.

## Facts checked against the code and the seed

Checked by running `migrate` and `seed_demo` on a fresh scratch SQLite database, and by reading the code:

- **CityCare has 4 usable O− red-cell units** with seed 7 (`available`, unexpired). The spec's Open question 3 assumed
  1 or 2. The bolt's claim that O− is "critically low" is not borne out. The scenario needs exactly one, so the seed
  change is required, as the spec proposes.
- **Seaview and Northside each have 2 available O− red-cell units** (donation numbers `901010`, `901011` and `902010`,
  `902011`), as the spec says. Both expire on the same instant, so expiry does not separate them.
- **The default blood strategy is `earliestExpiry`** (`apps/matching/scoring.py`: expiry 0.5, compatibility 0.2,
  distance 0.2, stock 0.1). Seaview and Northside tie on expiry, compatibility and stock, so distance decides the order.
  Seaview is nearer, so it ranks first. The scenario confirms the order on the page (S4).
- **Two actions use the browser's confirm dialog:** "Confirm receipt" (S9) and the allocate button on a hold (S10).
  Approve, dispatch and in transit do not ask. The spec names only S9's dialog, so S10 accepts one too.
- **Reservations have no Django admin page.** `apps/matching/admin.py` registers only `Allocation`. S12 reads the
  `reservation.created` entries from the audit list instead.
- **Login is a Django session.** The admin signs in once, so the same browser context can open `/admin/`.
- **Baseline on this branch, before any change:** backend ruff check and format, `makemigrations --check`, and pytest
  (1246 passed, 5 skipped) pass. Frontend lint, tests (423 passed) and build pass. `check_deploy_config.py` and
  `aidlc_board.py --check` pass.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 0 | Construction plan, and the approved inception spec (it was untracked on this branch) | `docs/aidlc/construction/2026-11-18-e2e-mvp-scenario.md`, `docs/aidlc/inception/2026-11-18-e2e-mvp-scenario.md` | Board and deploy-config checks |
| 1 | `seed_demo`: CityCare's usable O− red cells set to exactly one, after the random draws. Surplus usable units become `issued`. With none usable, the unexpired reserved or issued unit that expires last becomes available. Runs only on a fresh stock, like the rest of the blood seed | `backend/apps/core/management/commands/seed_demo.py`, `backend/apps/core/tests/test_seed_demo.py` | pytest: exactly one usable O− red cell at CityCare; reset repeats the same units and statuses; with the change switched off, every other unit's status is the same (only O− red cells differ); the 352-unit count is unchanged |
| 2 | Playwright project in `e2e/`: `package.json` with `@playwright/test` pinned exactly and a lockfile, `playwright.config.ts` (base URL from `E2E_BASE_URL`, one worker, Chromium only, list and HTML reporters, trace and screenshot on failure, no retries), `tsconfig.json` with a `typecheck` script, the six seeded accounts, and a `signIn` helper. `.gitignore` gets `e2e/playwright-report/` and `e2e/test-results/` | `e2e/package.json`, `e2e/package-lock.json`, `e2e/playwright.config.ts`, `e2e/tsconfig.json`, `e2e/tests/support/accounts.ts`, `e2e/tests/support/signIn.ts`, `.gitignore` | `npm ci`, `npm run typecheck`, `npx playwright test --list` |
| 3 | The scenario: steps S1 to S12, each titled with its §23 number, each asserting its spec row, with a precondition check at S4 | `e2e/tests/mvp-scenario.spec.ts` | The scenario itself, 3 consecutive local passes, each on a new database |
| 4 | Stable hooks in the frontend, only where a step cannot be found by role, label or the existing section id | None expected. If needed: the page, plus a Vitest test | `npm test`, `npm run build` |
| 5 | CI job `e2e` (triggers per spec Open question 1: pull requests, pushes to `main`, `workflow_dispatch`). Postgres 17 service, migrate, seed, runserver, vite build and preview, Playwright with browsers, report and traces uploaded on failure | `.github/workflows/ci.yml` | The workflow parses (validated with Ruby's YAML loader). The job's commands are run locally in the same order. The CI run itself needs a push, which this bolt does not do |
| 6 | Docs: `docs/testing/mvp-scenario.md` (how to run it locally, the §23 mapping table, what CI runs), a link from `docs/testing/README.md`, and a short "End-to-end scenario" section in `README.md` | `docs/testing/mvp-scenario.md`, `docs/testing/README.md`, `README.md` | Every local command in the docs run as written |

## Sequencing

0 → 1 → 2 → 3 → 4 (only if 3 needs it) → 5 → 6.

Unit 3 needs unit 1: without the seed change, S4's precondition (one or two usable units at CityCare) fails. Unit 5 needs
unit 3 for the job to have something to run. Unit 6 documents what units 3 and 5 do, so it comes last.

## Test plan

- **Backend, every commit:** `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && python -m pytest -q`.
- **Frontend, every commit that touches it:** `cd frontend && npm run lint && npm test && npm run build`.
- **Repo, every commit:** `python3 scripts/check_deploy_config.py && python3 scripts/aidlc_board.py --check`.
- **Scenario, locally, before the final commit:** a new SQLite database per run (`migrate`, `seed_demo`), then
  `runserver localhost:8000`, `npm run build` and `npm run preview -- --host localhost --port 5173 --strictPort`, then
  `npx playwright test` in `e2e/`. Three consecutive passes, each on a new database. Every run stops its servers.
- **Scenario, in CI:** the `e2e` job on the pull request. The bolt's exit requires three consecutive green runs of the same
  commit before `status: Done`. That is a human step after the push.
- **What the scenario proves** is mapped criterion by criterion in `docs/testing/mvp-scenario.md` (unit 6).

## Decisions and deviations from the spec

- **Surplus O− units become `issued`, not deleted.** This keeps the unit count and the other random draws unchanged.
  An issued unit has already left the shelf, so the one usable unit left is the only one a case can reserve.
- **S10 accepts the allocate confirmation too.** The spec mentions only S9's dialog. The same test step cannot be
  reached without it.
- **Reservations are checked through the audit log in S12**, because there is no Reservation admin page.
- **The admin's Django page is opened on `E2E_ADMIN_URL`** (default `http://localhost:8000/admin/`). The spec names no
  variable for it. It mirrors `E2E_BASE_URL`, and nothing else reads it.
- **`--noreload` is not used on `runserver`.** The spec's command is kept as written.
- **`workflow_dispatch` is added to the workflow's top-level `on:`, so a manual run runs every job.** The spec asks for
  manual runs and keeps the existing triggers. The other jobs have no `if:`, so they run on a manual run too. That is a
  full check of the branch, and it is the cost of putting the trigger on the workflow.
- **Playwright is pinned at 1.64.1, not the newest 1.65.1.** 1.65.1 was published five days before this bolt. 1.64.1 is
  the newest release at least two weeks old. TypeScript and `@types/node` match the versions the frontend locks.
- **No frontend change (unit 4 is empty).** Every step found its element by role, label or the page's section id.
- **The local runs use SQLite; CI uses PostgreSQL 17.** Unit 5's job has not run on PostgreSQL. See Verification.

## Verification

- **Backend** (after unit 1): `ruff check .`, `ruff format --check .` and `makemigrations --check --dry-run` pass.
  `pytest -q`: 1251 passed, 5 skipped. The baseline was 1246 passed, 5 skipped, and the five new seed tests account for
  the difference.
- **Scenario** (after unit 3, the final spec): three consecutive passes, each on a freshly seeded SQLite database, took
  5.7 s, 6.0 s and 6.5 s. A negative check with four usable O− units (the seed change undone) failed at S4 with the
  precondition message: "Precondition: CityCare has 1 or 2 usable O− red cells (seed_demo sets exactly 1)".
- **Repo**: `check_deploy_config.py` and `aidlc_board.py --check` pass after each commit.
- **Not verified here:** the `e2e` job on GitHub, and the scenario on PostgreSQL 17. The sandbox refused to run a
  downloaded PostgreSQL binary, so the database is SQLite. The bolt's "three consecutive CI runs" criterion needs a push
  and a human to check the runs.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that approval is
the Construction gate.
