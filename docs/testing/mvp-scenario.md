# MVP acceptance scenario (end-to-end test)

The proposal's §23 scenario, run as one browser test against the real API, database and built frontend:
a hospital asks for critical blood, the system finds compatible units across the network, the units are
reserved, a supplying hospital approves a transfer, and the receiving hospital confirms receipt.

- Test: [`e2e/tests/mvp-scenario.spec.ts`](../../e2e/tests/mvp-scenario.spec.ts) (one serial test, steps S1 to S12)
- CI: the `e2e` job in [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)
- Spec: [inception](../aidlc/inception/2026-11-18-e2e-mvp-scenario.md) · plan:
  [construction](../aidlc/construction/2026-11-18-e2e-mvp-scenario.md) · bolt [B12](../aidlc/bolts/B12-e2e-mvp-scenario.md)

## Who the scenario plays

Every login is one `seed_demo` creates (README "Signing in"; password `CityCare-demo-1`). Each one signs in through
`/login` in its own browser context.

| Login | What it does in the scenario |
|---|---|
| `nurse@demo.citycare.pk` | Opens the critical request, reserves local stock, asks Seaview for the shortfall, closes the case |
| `bloodbank@demo.citycare.pk` | Checks CityCare's stock, confirms receipt, allocates the held unit |
| `admin@demo.citycare.pk` | Checks the hospitals; acts as Seaview's supplier (approve, dispatch, in transit); reads the Django admin |
| `doctor@demo.citycare.pk` | Reads the case history and the transfer panel |

## The steps

Each step's title starts with its §23 number. The step asserts what the table says. The numbers in it (local
stock, shortfall, quantities) are read from the page, not assumed.

| Step | Criterion | What the browser does | Asserts |
|---|---|---|---|
| S1 | 1 | Admin opens Hospitals | Three hospitals, all active |
| S2 | 2 | Blood bank opens Blood bank; filters to Issued | CityCare has O− red cells in stock; the issued units are listed as issued |
| S3 | 3 | Nurse sends a critical request: O−, red cells, 3 units | A new case, status Open, need "3 × O− red cells" |
| S4 | 4, 5 | Nurse reads the case, then its sources | Local stock is 1 or 2 units (precondition); Seaview is ranked above Northside; each has 2 available; "Ordered by earliest expiry first"; "Why this score?" shows the points |
| S5 | 6 | Nurse reserves the local units | The holds show as Held; status Matching; the timeline says "System" moved it |
| S6 | 6 | Nurse opens a second critical request for 1 O− unit | "Available here: 0", no reserve form; the case is then cancelled |
| S7 | 7 | Nurse requests the shortfall from Seaview | Transfer requested, quantity = shortfall; listed under Outgoing with the case |
| S8 | 8 | Admin, for Seaview: Approve, Mark dispatched, Mark in transit | Each status in turn; two units set aside |
| S9 | 8, 9 | Blood bank: Confirm receipt (accepts the confirm) | Transfer Delivered; the units are CityCare's and issued; case Partially fulfilled |
| S10 | 9 | Blood bank allocates the local hold (accepts the confirm) | Case Fulfilled; "Every need allocated" |
| S11 | 10 | Nurse closes the case with an outcome note | Case Closed; the outcome shows |
| S12 | 10 | Doctor reads the history; admin reads the transfer, allocation and audit lists | Every move shows its actor; the audit list has the transfer, reservation and allocation entries |

Two of these steps accept a browser confirm: "Confirm receipt" (S9) and "Allocate" (S10). The spec named only S9.

## What §23 each step covers

| §23 criterion | Steps | Status | Reason, if not full |
|---|---|---|---|
| 1. At least three hospitals, synthetic data | S1, S4 | Covered | |
| 2. Each hospital maintains its blood inventory with unit-level status | S2 (CityCare), S8 (the Seaview units the admin sets aside) | Partial | No blood-bank login exists at Seaview or Northside. Registering and changing units is not in the scenario; the blood tests cover it |
| 3. A hospital submits a critical blood request | S3 | Covered | |
| 4. Compatible, approved, unexpired and unreserved units found across the network | S4 (Seaview's and Northside's O− units offered), S5 and S8 (held units leave the search) | Partial | Only the positive path is asserted here. Quarantined, expired, reserved and incompatible units are covered by the blood and matching pytest suites. "Approved" means status `available` |
| 5. Candidates ranked by documented allocation rules | S4 | Covered | The rules are in [docs/setup/deployment.md](../setup/deployment.md) ("Candidate scoring") |
| 6. Selected units reserved without being allocated to another request at the same time | S5, S6, S8 | Covered for one competing case | Real parallel races are covered by the concurrency tests of #44, not by the browser |
| 7. Inter-hospital transfer started when stock is short | S7 | Covered | |
| 8. Supplier approves; units move through defined transfer states | S8, S9 | Covered | The admin acts for Seaview (spec Open question 2) |
| 9. Receipt confirmed; inventory and request states update | S9, S10 | Covered | |
| 10. Complete transaction history visible to authorised users | S11, S12 | Partial | No in-app audit view until B10 (#56). The Django admin audit list is read-only, and only the admin opens it |
| 11. Complete workflow covered by automated tests of its core rules | The whole `e2e` job, with the pytest suites | Covered jointly | The browser test checks the workflow; rule-level coverage is in the pytest suites |

Criteria 2, 4 and 10 are partial for the reasons above. Nothing in §23 is left out.

Reservations have no Django admin page. S12 checks their audit entries (`reservation.created`) instead.

## Run it locally

You need Python 3.13 with `backend/requirements-dev.txt`, Node 24, and the Chromium browser for Playwright.
Start three things, in order. The scenario needs a **fresh database**: each run uses up the stock it reserves, and
the next run would find none left. The default database is `backend/db.sqlite3`; delete it to start over.

```bash
# 1. The API on http://localhost:8000, on a fresh database
cd backend
python manage.py migrate
python manage.py seed_demo
python manage.py runserver localhost:8000

# 2. The frontend on http://localhost:5173, built as CI builds it (in another terminal)
cd frontend
npm ci
npm run build
npm run preview -- --host localhost --port 5173 --strictPort

# 3. The scenario (in a third terminal)
cd e2e
npm ci
npx playwright install chromium    # on Linux CI uses: npx playwright install --with-deps chromium
npm test                           # or: npx playwright test --reporter=list
```

Port 5173 is fixed because the API accepts only `http://localhost:5173` by default (`CORS_ALLOWED_ORIGINS`,
`CSRF_TRUSTED_ORIGINS`). The API must run with `DJANGO_DEBUG` on (the default), or its session cookies become
`Secure` and the plain-http local setup can't use them.

Environment variables, if you need them:

- `E2E_BASE_URL` (default `http://localhost:5173`): the frontend the scenario opens.
- `E2E_ADMIN_URL` (default `http://localhost:8000/admin/`): the Django admin used in S12.

After a failure, `e2e/playwright-report` (open with `npx playwright show-report`) and `e2e/test-results` hold the
screenshot and the trace of each failed step. `npx playwright show-trace <trace.zip>` replays it.

## What CI runs

The `e2e` job runs on pull requests, on pushes to `main`, and on a manual run. It is not run on every push to every
branch, because it is the slowest job. It starts PostgreSQL 17, migrates and seeds, starts `runserver` on port 8000,
builds the frontend and serves it with `vite preview` on port 5173, then runs the scenario. A failing step fails the
job. On failure it uploads the Playwright report and traces as the `e2e-report` artifact.

The scenario has no retries. A flaky step is a bug to fix (a wait on something visible), not a retry to hide.

## Limits

- Desktop Chromium only. No mobile layouts, no visual comparisons.
- Load and concurrency are out of scope: load testing is B13 (#58).
- Equipment and beds are not transferred, so the scenario moves only blood (spec Open question 4).
- The scenario depends on the seed: CityCare has exactly one usable O− red-cell unit (`seed_demo`), and each partner
  has two. Changing the demo stock means changing the scenario too.
