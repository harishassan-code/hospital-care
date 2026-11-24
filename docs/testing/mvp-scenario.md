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
| `admin@demo.citycare.pk` | Checks the hospitals; acts as Seaview's supplier (approve, dispatch, in transit); reads the Transfers page and the audit log |
| `doctor@demo.citycare.pk` | Reads the case history and the transfer panel |

## The steps

Each step's title starts with its §23 number. The step asserts what the table says. The numbers in it (local
stock, shortfall, quantities) are read from the page, not assumed.

| Step | Criterion | What the browser does | Asserts |
|---|---|---|---|
| S1 | 1 | Admin opens Hospitals | The scenario's three hospitals among the network (ten since B20), every one active |
| S2 | 2 | Blood bank opens Blood bank; filters to Issued | CityCare has O− red cells in stock; the issued units are listed as issued |
| S3 | 3 | Nurse sends a critical request: O−, red cells, 3 units | A new case, status Open, need "3 × O− red cells" |
| S4 | 4, 5 | Nurse reads the case, then its sources | Local stock is 1 or 2 units (precondition); Seaview ranks first, with 2 available (its units expire first in the network, B20); Northside is offered too; "Ordered by earliest expiry first"; "Why this score?" shows the points |
| S5 | 6 | Nurse reserves the local units | The holds show as Held; status Matching; the timeline says "System" moved it |
| S6 | 6 | Nurse opens a second critical request for 1 O− unit | "Available here: 0", no reserve form; the case is then cancelled |
| S7 | 7 | Nurse requests the shortfall from Seaview | Transfer requested, quantity = shortfall; listed under Outgoing with the case |
| S8 | 8 | Admin, for Seaview: Approve, Mark dispatched, Mark in transit | Each status in turn; two units set aside |
| S9 | 8, 9 | Blood bank: Confirm receipt (accepts the confirm) | Transfer Delivered; the units are CityCare's and issued; case Partially fulfilled |
| S10 | 9 | Blood bank allocates the local hold (accepts the confirm) | Case Fulfilled; "Every need allocated" |
| S11 | 10 | Nurse closes the case with an outcome note | Case Closed; the outcome shows |
| S12 | 10 | Doctor reads the history; admin reads the transfer on the Transfers page and searches the in-app audit log (B10) | Every move shows its actor; the audit log has each of the transfer's five moves once, with who made it (searched by the transfer's id), and the case's 3 holds, 3 allocations and the nurse's close (searched by its reference) |

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
| 10. Complete transaction history visible to authorised users | S11, S12 | Covered | The doctor reads the case's history and transfers; the admin reads the transfer and searches the in-app audit log (B10, #56) for this run's records. No Django admin is used, so the check holds on staging too, where it is off (B13) |
| 11. Complete workflow covered by automated tests of its core rules | The whole `e2e` job, with the pytest suites | Covered jointly | The browser test checks the workflow; rule-level coverage is in the pytest suites |

Criteria 2 and 4 are partial for the reasons above. Criterion 10 was partial until the in-app audit log (B10) was
merged; S12 now uses it. Nothing in §23 is left out.

S12 counts only this run's records. The transfer's moves are searched by its id. The holds, allocations and close are
searched by the case reference, less what S3 found already filed under it, because `seed_demo --reset` starts
references again at `EC-<year>-0001` and keeps the audit log.

## Run it locally

You need Python 3.13 with `backend/requirements-dev.txt`, Node 24, and the Chromium browser for Playwright.
Start three things, in order. The scenario needs the seeded stock: each run uses up what it reserves. Before running
it again on the same database, run `python manage.py seed_demo --reset` (or delete the default database,
`backend/db.sqlite3`, and seed again).

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

After a failure, `e2e/playwright-report` (open with `npx playwright show-report`) and `e2e/test-results` hold the
screenshot and the trace of each failed step. `npx playwright show-trace <trace.zip>` replays it.

## What CI runs

The `e2e` job runs on pull requests, on pushes to `main`, and on a manual run. It is not run on every push to every
branch, because it is the slowest job. It starts PostgreSQL 17, migrates and seeds, starts `runserver` on port 8000,
builds the frontend and serves it with `vite preview` on port 5173, then runs the scenario. A failing step fails the
job. On failure it uploads the Playwright report and traces as the `e2e-report` artifact.

The scenario has no retries. A flaky step is a bug to fix (a wait on something visible), not a retry to hide.

## Against production settings (staging rehearsal, 22 Nov)

Staging isn't deployed yet (#69), so the scenario was run once against the same set-up locally, to catch anything
that only breaks with DEBUG off:

- **API:** a fresh PostgreSQL 16 database, built with `render.yaml`'s build steps (`collectstatic`, `migrate`,
  `seed_demo`) and its environment: `DJANGO_DEBUG=false`, a random 50-character secret key, `DJANGO_HSTS_SECONDS=3600`,
  `DJANGO_ADMIN_ENABLED=false`, `DJANGO_TRUSTED_PROXY_COUNT=1`, and `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`
  set to the site's address. Started with `render.yaml`'s start command, `gunicorn config.wsgi:application`.
- **Site:** built with `VITE_API_URL=/api`, as on Vercel, and served by a small local proxy standing in for
  `frontend/vercel.json`. It forwards `/api/*` to gunicorn with a different `Host` and `X-Forwarded-Proto: https`, as
  Vercel and Render's edge do.

Results: `check --deploy --fail-level WARNING` found no issues; `scripts/smoke_staging.py` passed; the session and
CSRF cookies came back `Secure; SameSite=None`; plain HTTP straight to the API was redirected to HTTPS; and **the
whole scenario passed** (314 API requests, none answered 4xx or 5xx). What this can't check is Render and Vercel
themselves: the real hostnames, TLS, and the proxy count behind Render's edge (security review, decision 2).

## Against Vercel's build output (staging rehearsal, 23 Nov)

Staging moved to one Vercel project (deployment guide). Before anyone deploys it, the scenario ran against what
Vercel itself would deploy:

- **Build:** the real Vercel CLI (`vercel build --prod`, CLI 66.6) on a clean copy of the branch, with only
  `DJANGO_SECRET_KEY` and a database set, as on the real project. Both services built: the site (with
  `VITE_API_URL=/api`) and the API, whose build step ran `check --deploy` (*System check identified no issues (1
  silenced).*), the migrations over `DATABASE_URL_UNPOOLED` (the pooled `DATABASE_URL` was deliberately unreachable,
  to prove the direct one is used), `createcachetable` and `seed_demo`, then Vercel's own `collectstatic`.
- **API:** the built function, run with Vercel's own Python runtime (`vercel_runtime`, the code that turns a request
  into WSGI on Vercel) on Python 3.13, against PostgreSQL 16, with `VERCEL=1` and nothing else but the key and the
  database.
- **Site and routing:** a small HTTPS stand-in for Vercel's edge that follows the routes `vercel build` wrote
  (`/api/*` to the API, files, then `index.html`), on a `*.vercel.app` hostname with TLS, setting `X-Forwarded-For` to
  the visitor's address as Vercel does.

Results: `scripts/smoke_staging.py` passed; deep links such as `/staff/beds` got the app; **the whole scenario passed**
(12.1 s, 292 API requests, none answered 4xx or 5xx); and the sign-in limit was counted in the database
(`django_cache`), where every copy of the API sees it. What this can't check is Vercel's own edge and Neon.

## Limits

- Desktop Chromium only. No mobile layouts, no visual comparisons.
- Load and concurrency are out of scope: load testing is B13 (#58).
- Equipment and beds are not transferred, so the scenario moves only blood (spec Open question 4).
- The scenario depends on the seed: CityCare has exactly one usable O− red-cell unit (`seed_demo`), and each partner
  has two. Changing the demo stock means changing the scenario too.
