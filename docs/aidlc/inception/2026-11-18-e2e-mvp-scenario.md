# Inception Spec: End-to-end MVP scenario test

**Date:** 2026-11-18
**Author:** Claude, drafted for review
**Related backlog item:** [#57](https://github.com/harishassan-code/hospital-care/issues/57) Automate the MVP acceptance
scenario (Epic E0, Sprint 9; bolt [B12](../bolts/B12-e2e-mvp-scenario.md)). Builds on the transfer stories
[B01](2026-11-18-transfer-request.md), [B02](2026-11-18-transfer-tracking.md) and
[B03](2026-11-18-delivery-confirmation.md), and on the reservation, allocation and matching work.

## Problem

The MVP is complete when the team can show one scenario (proposal §23): a hospital asks for critical blood, the system
finds compatible units across the network, units are reserved, a supplying hospital approves a transfer, and the
receiving hospital confirms receipt. Today each link is tested on its own: pytest for each backend module, and Vitest
page tests against a fake server. Nothing runs the whole chain in a real browser against the real API and database, so
a change that breaks a hand-off between two modules can pass CI. Sprint 9 says no new features ship unless this
scenario is green (`docs/scrum/timeline.md`).

This is for the team (CI must go red when the chain breaks), for the Product Owner (evidence for each §23 criterion at
the sprint review), and for the people the scenario plays:

| Role | Seeded login (password `CityCare-demo-1`) | What the scenario does with it |
|---|---|---|
| Nurse (emergency coordinator) | `nurse@demo.citycare.pk` | Opens the case, reserves local stock, requests the transfer, closes the case |
| Blood bank | `bloodbank@demo.citycare.pk` | Confirms receipt and allocates the held units at CityCare General |
| Admin | `admin@demo.citycare.pk` | Plays the supplier at Seaview Hospital (see Open question 2) |
| Doctor | `doctor@demo.citycare.pk` | Reads the case and transfer history |

## User stories

- As the team, we want the MVP scenario to run in CI in a real browser, so that a change that breaks the chain from
  request to receipt fails the build before it merges. (#57)
- As the Product Owner, I want each criterion in proposal §23 mapped to a step the test runs, so that the sprint review
  shows evidence rather than a claim.
- As an emergency coordinator at CityCare General, I want to open a critical blood request and see which hospitals can
  supply the shortfall, ranked, so that I ask the right hospital for the right stock.
- As the blood bank at CityCare General, I want to confirm receipt of transferred units, so that the stock moves to my
  hospital and the request updates.
- As a supplying hospital, I want to approve, dispatch and track a transfer, so that my stock is set aside and every move
  is recorded.

## Acceptance criteria

The bolt's two criteria, kept and made testable:

- [x] **The scenario runs in CI.** A job `e2e` in `.github/workflows/ci.yml` starts PostgreSQL 17, runs `migrate` and
      `seed_demo`, starts `runserver` and `vite preview`, and runs the Playwright scenario. Any failing step fails the job.
      On failure the job uploads the Playwright report and traces. *(22 Nov: green on pull request #124, runs [1](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/1), [2](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/2), [3](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/3),
      and on `main` after the merge.)*
- [x] **The scenario covers every MVP acceptance criterion in the proposal (§23).** The eleven numbered criteria in
      `docs/product/source/CityCare_Project_Proposal.docx`, section 23, each map to a step of the scenario (see the mapping
      table). Three are partial, with the reason stated there. None is left out. Each step title starts with its §23 number.
      *(22 Nov: two are partial now. §23.10 is Covered since construction unit 7 moved S12 to the in-app audit log.)*

Added so the two criteria can be checked:

- [x] The scenario lives in its own Playwright project in `e2e/`. `frontend/package.json` does not change.
- [x] Every number the scenario checks is read from the app during the run. The scenario asserts its seed preconditions
      (Design, Preconditions) and fails with a message that names the precondition. It never skips.
- [x] The scenario uses only the browser and the seeded logins from README "Signing in". It adds no test-only endpoints.
- [x] The scenario is green on three consecutive CI runs of the same commit before the bolt is set to Done.
      *(Commit `d9688b4`, pull request #124: runs [1](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/1), [2](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/2), [3](https://github.com/harishassan-code/hospital-care/actions/runs/45059846515/attempts/3).)*
- [x] No real patient data, names or secrets are added. The demo password is the one already published in the README.

## Non-goals

- Load and stress testing (B13, #58). Concurrency is covered by the backend tests of #44.
- Running the scenario against staging (Render, Vercel). Staging checks belong to B14 (#59).
- Beds, operating rooms, ambulances and patient transfer (B17). The transfer rules move only blood and equipment
  (`TRANSFERABLE` in `apps/transfers/services.py`).
- Equipment transfers in the scenario. §23 is about blood units, and equipment is listed as a future extension (§5.2).
- Notifications (B06, B07). §23 does not ask for them.
- Browsers other than desktop Chromium, mobile layouts, and screenshot or visual comparisons.
- Business-rule changes. The only changes allowed are seed data and CI configuration, and only if Open questions 2 and 3
  are approved.

## Design

### Dependencies and the state of the code

- B12 depends on B03. The board shows B01 to B03 as "In Review", but their code is already on `main` (commit `74edf28`,
  #102). This spec assumes that code as it is on `main`. A human confirms the board before Construction starts.
- Playwright is not in the repo. It appears in `frontend/package-lock.json` only as an optional peer of Vitest.

### Playwright project layout

```
e2e/
  package.json                 @playwright/test (exact version), script "test"
  package-lock.json
  playwright.config.ts         baseURL http://localhost:5173 (E2E_BASE_URL overrides); one worker; Chromium;
                               reporters list and html; trace and screenshot on failure; no webServer block
  tests/mvp-scenario.spec.ts   one serial test, steps S1 to S12, titled with their §23 numbers
  tests/support/accounts.ts    the six seeded emails and the demo password
  tests/support/signIn.ts      signs in at /login (fields labelled "Email" and "Password"), waits for /staff
```

`.gitignore` gets `e2e/playwright-report/` and `e2e/test-results/`. `node_modules/` is already ignored.

### Preconditions from `seed_demo` (read from the code, not yet run)

- Three active hospitals: CityCare General (the hospital every seeded login works at), Seaview Hospital and Northside
  Children's Hospital (`HOSPITALS`).
- Every seeded login is attached to CityCare General, the admin included (`seed_users`). So admin's own-hospital list
  views (cases, blood units, holds) show only CityCare. The network-wide views are the hospitals list and the transfers
  list.
- Seaview and Northside each get exactly two available red-cell units of every blood group, collected five days ago and
  expiring in 37 days (`seed_partner_stock`). For an O- red-cell need, each partner therefore has exactly two candidate
  units. Seaview is nearer to CityCare General by the seeded coordinates (about 6 km against about 10 km, a rough
  estimate), so it ranks first by the default blood strategy.
- Each partner also has one available ventilator and one monitor. CityCare has two available ventilators.
- CityCare's own blood is drawn at random from seed 7, so its usable O- red-cell count (L) is unknown from the code.
  The bolt's claims that O- is "critically low" and that CityCare has no free ICU bed were not checked by running the seed.
  The ICU claim cannot drive the transfer step anyway, because beds do not transfer.
- The partner units have no screening rows (`TestResult`). In the scenario, "approved" means status `available`, which is
  what `usable_units` checks.

### Scenario steps

Quantities are chosen so the seeded numbers meet in the middle: the case asks for 3 O- red-cell units. Preconditions
(asserted at S4): 1 <= L <= 2, and Seaview is listed as a candidate for the line. Then the shortfall is 3 - L, which
Seaview's two units cover.

| Step | Who | What the browser does | Endpoint behind it (`backend/config/urls.py`) | Asserts | §23 |
|---|---|---|---|---|---|
| S1 | admin | Opens Hospitals (`/staff/hospitals`) | `GET /api/hospitals/` | Three hospitals, all active | 1 |
| S2 | blood bank | Opens Blood bank (`/staff/blood`) | `GET /api/blood/units/`, `/api/blood/stock/` | CityCare's units with their statuses are shown | 2 (partial) |
| S3 | nurse | Emergencies, "Request blood": Critical, O-, Red cells, 3 units | `POST /api/emergencies/` | Redirected to `/staff/emergencies/EC-2026-NNNN`, status Open, need "3 × O- red cells" | 3 |
| S4 | nurse | Case page: "Available here: L · Short: 3-L", then "Sources in the network" | `GET /api/emergencies/<ref>/`, `GET .../candidates/` | Preconditions hold. Seaview is listed above Northside. The panel says "Ordered by earliest expiry first". "Why this score?" shows the factor points | 4, 5 |
| S5 | nurse | "Reserve L here" | `POST /api/emergencies/<ref>/reservations/` | L holds under Reservations. Case status Matching, timeline entry by "System" | 6 |
| S6 | nurse | Opens a second Critical case for 1 O- red-cell unit | `POST /api/emergencies/` | "Available here: 0", no "Reserve here" form, held units not offered. The second case is then cancelled | 6 |
| S7 | nurse | Case page, Sources: "Request 3-L from Seaview Hospital" | `POST /api/transfers/` | Transfer Requested, listed under Outgoing with the case reference | 7 |
| S8 | admin | Transfers, Outgoing tab: Approve, Mark dispatched, Mark in transit | `POST /api/transfers/<id>/actions/` (three moves) | Status Requested, Approved, Dispatched, In transit. The Seaview units named under "resources" | 8 |
| S9 | blood bank | Transfers, Outgoing tab: Confirm receipt (accepts the browser confirm dialog) | `POST /api/transfers/<id>/actions/` `deliver` | Status Delivered. The units now belong to CityCare, status issued. Case status Partially fulfilled | 9 |
| S10 | blood bank | Case page, Reservations: Allocate each local hold | `POST /api/reservations/<id>/allocate/` | Case status Fulfilled, timeline "Every need allocated" | 9 |
| S11 | nurse | Case page, Update status: close with an outcome note | `POST /api/emergencies/<ref>/actions/` `close` | Case status Closed | 10 |
| S12 | doctor, then admin | Doctor: case page, Status history and Transfers panel. Admin: `/admin/`, Audit logs list, reading the transfer, reservation and allocation records | `GET /api/emergencies/<ref>/`, `GET /api/transfers/` | Every move appears with its actor. The admin sees the audit records | 10 |

Notes on the steps:

- S8 uses the Outgoing tab because admin is attached to CityCare General. The Incoming tab filters to transfers CityCare
  supplies, and this one is supplied by Seaview. The case page's Transfers panel is read-only; it only links to the
  Outgoing tab, so it cannot make the moves.
- The audit admin filters on an exact action name, not a prefix, so S12 reads the list rather than filtering it.
- The local holds from S5 last `RESERVATION_HOLD_MINUTES` (30). The whole run from S5 to S10 should take a few minutes. A
  slower run that lets a hold expire would fail at S10 with a 409, which is correct behaviour and not a flake to retry.
- Critical cases escalate after `EMERGENCY_ESCALATION_MINUTES` (30) in one status. Escalated cases can still reserve and
  allocate, so this does not break the scenario.
- S9 has a confirm dialog. The test accepts it explicitly.

### §23 mapping

| §23 criterion | Covered by | Status | Reason, if not full |
|---|---|---|---|
| 1. At least three hospitals, synthetic data | S1; Northside appears in S4 | Covered | |
| 2. Each hospital maintains its blood inventory with unit-level status | S2 for CityCare. Seaview is handled by the admin in S8 | Partial | No blood-bank login exists at the partner hospitals (Open question 2). Registering and changing units is not in the scenario; the blood tests cover it |
| 3. A hospital submits a critical blood request | S3 | Covered | |
| 4. Compatible, approved, unexpired, unreserved units found across the network | S4 (Seaview's and Northside's O- units offered); S5 and S8 (held units leave the search) | Partial | Only the positive path is asserted here. The exclusions (quarantined, expired, reserved, the compatibility table) are covered by the blood and matching pytest suites. "Approved" means status available |
| 5. Candidates ranked by documented allocation rules | S4. Rules documented in `docs/setup/deployment.md` ("Candidate scoring") and `docs/architecture/api.md` | Covered | |
| 6. Selected units reserved without being allocated to another request at the same time | S5 (reserve), S6 (a competing case gets nothing), S8 (approval holds at the supplier) | Covered for one competing case | True parallel races are covered by the #44 concurrency tests, not by the browser |
| 7. Inter-hospital transfer started when stock is short | S7 | Covered | |
| 8. Supplier approves; units move through defined transfer states | S8 (Requested, Approved, Dispatched, In transit), S9 (Delivered) | Covered | Admin acts for Seaview (Open question 2) |
| 9. Receipt confirmed; inventory and request states update | S9 (units at CityCare, case Partially fulfilled), S10 (case Fulfilled) | Covered | |
| 10. Complete transaction history visible to authorised users | S11, S12: case timeline, transfer history, Django admin audit list for the admin | Partial | No in-app audit view exists until B10 (#56). The Django admin audit list is read-only and only the admin can open it (Open question 5) |
| 11. Complete workflow covered by automated tests of its core rules | The whole `e2e` job, together with the existing pytest suites for blood, matching, reservations and transfers | Covered jointly | The browser test checks the workflow. Rule-level coverage comes from the pytest suites |

Nothing in §23 is uncovered. Criteria 2, 4 and 10 are partial, for the reasons above.

### CI job

A job `e2e` in `.github/workflows/ci.yml`, separate from `backend` and `frontend`:

- Triggers: as proposed in Open question 1. The job has its own `if:` so the workflow's existing triggers stay as they are.
- `timeout-minutes: 20`.
- Service container `postgres:17`, with the same credentials, port and health check as the `backend` job. `DATABASE_URL`
  is set to the same URL.
- Steps, in order:
  1. Check out. Set up Python 3.13 with pip cache keyed on `backend/requirements-dev.txt`. Run
     `pip install -r requirements-dev.txt`.
  2. In `backend`: `python manage.py migrate`, then `python manage.py seed_demo`.
  3. Start the API in the background with `python manage.py runserver localhost:8000`. Wait until
     `http://localhost:8000/api/health/` answers.
  4. Set up Node 24 with npm cache keyed on `frontend/package-lock.json`. In `frontend`: `npm ci`, then `npm run build`.
     The build uses the default `VITE_API_URL` (`http://localhost:8000/api`).
  5. Start the UI in the background with `npm run preview -- --host localhost --port 5173 --strictPort`. Wait until
     `http://localhost:5173` answers.
  6. In `e2e`: `npm ci`, then `npx playwright install --with-deps chromium`, then `npx playwright test`.
  7. On failure, upload `e2e/playwright-report` and `e2e/test-results` as artifacts.

Points that matter:

- Port 5173 is fixed on purpose. `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` default to `http://localhost:5173`
  (`config/settings.py`), and `vite preview` defaults to port 4173. A different port needs both variables set.
- Keep `DJANGO_DEBUG` at its default (true). Otherwise the session cookies become `Secure` and `SameSite=None`
  (`config/settings.py`), which the plain-http local setup does not match.
- Both servers bind to `localhost`, the name the browser uses.
- The service container is empty at the start of every run, so `seed_demo` always runs on a fresh database.
- Locally, a second run needs a new database. `seed_demo --reset` cannot clear a database that has cases or transfers:
  cases, transfers and holds all protect their hospital (`on_delete=PROTECT`). This is from reading the models, not from
  running the command.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off.

1. **Run on every push, or only on PRs to `main`?** *Proposed:* run the job on pull requests (the existing `pull_request`
   trigger, with no branch filter) and on pushes to `main`, plus `workflow_dispatch` for manual runs. Not on every push
   to every branch. The job is the slowest in the workflow (browser download, production build, seed, browser run), and
   the other jobs already run on every push and catch the same breakage early. No path filters, because a skipped
   required check is easy to miss.
2. **Who plays the supplier at Seaview and Northside?** Every seeded login works at CityCare General. The only seeded
   login that can approve, dispatch or mark in transit at Seaview is the admin (`may_act` in `apps/transfers/services.py`).
   *Proposed:* use the admin for the supplier steps in the first cut, which needs no seed change. Decision for the PO: add
   one blood-bank login per partner hospital to `seed_demo` and to the README table. That is a small seed change, and it
   would let S8 run as Seaview's own blood bank.
3. **Should CityCare's O- stock stay random?** S4 needs one or two usable O- red-cell units at CityCare, and seed 7 does
   not guarantee that. *Proposed:* after the random draws, `seed_demo` sets CityCare's usable O- red-cell count to exactly
   one, so the other demo data keeps its draws. The scenario then runs with L = 1: request 3, reserve 1 locally, transfer
   2 from Seaview. Alternatives: (a) keep the random data and let the test read L, which skips the local reservation when
   L is 0; (b) run the scenario on ventilators, which are fixed in the seed (CityCare 2, each partner 1). §23 asks for
   blood, so (b) would be a second scenario.
4. **Blood only, or also equipment?** *Proposed:* blood only, because §23 is written for blood units (compatible, approved,
   unexpired units and blood-unit transfers). Equipment can get its own scenario later.
5. **Does the scenario check the audit log in Django admin?** Until B10 (#56) there is no in-app audit view, and the Django
   admin list is read-only. *Proposed:* yes, S12 checks it for the admin only. §23.10 stays partial until B10 lands.
6. **Retries.** *Proposed:* no automatic retries (`retries: 0`). A failing run is a real signal, and a retry would hide a
   race. If a step is flaky, fix the wait (wait for visible text or for the response), not the retry count.

## Approval

- [x] Approved by: Krrishna on 2026-11-18 (proposed answers accepted as written)
