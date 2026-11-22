# Construction Plan: Security and performance hardening

**Spec:** [docs/aidlc/inception/2026-11-18-security-performance.md](../inception/2026-11-18-security-performance.md)
**Date:** 2026-11-18
**Bolt:** [B13](../bolts/B13-security-performance.md), issue [#58](https://github.com/harishassan-code/hospital-care/issues/58)

## Units of work

Each unit is one commit, built and checked in order. Units 3 to 5 tighten access; unit 6 adds the
throttle; units 7 to 9 are the seed option and the load test; unit 10 writes the review.

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | **Deploy hardening (F8, deploy checks).** Refuse to start with DEBUG off and no `DJANGO_SECRET_KEY`. HSTS (`DJANGO_HSTS_SECONDS`, default 3600, includeSubDomains, no preload) and SSL redirect with `api/health/` exempt, only when DEBUG is off. Same HSTS header on the Vercel domain (spec Q6). CI runs `check --deploy` with a dummy key. | `backend/config/settings.py`, `render.yaml`, `frontend/vercel.json`, `backend/.env.example`, `docs/setup/deployment.md`, `.github/workflows/ci.yml`, `backend/apps/core/tests/test_deploy_settings.py` (new) | Subprocess tests with DEBUG off: `check --deploy --fail-level WARNING` is clean with a 50+ character key; `check` without a key exits non-zero and names `DJANGO_SECRET_KEY`; `/api/health/` is not redirected while another API path is; HSTS and redirect settings are off under DEBUG (the test suite). |
| 2 | **Django admin gated (F6, spec Q7).** `/admin/` is routed only when `DJANGO_ADMIN_ENABLED` is true, which defaults to on under DEBUG and off otherwise. Render sets it off explicitly. | `backend/config/settings.py`, `backend/config/urls.py`, `render.yaml`, `backend/.env.example`, `docs/setup/deployment.md`, `backend/apps/core/tests/test_admin_route.py` (new) | Subprocess tests: with DEBUG off `/admin/` does not resolve; with `DJANGO_ADMIN_ENABLED=true` it does. In-process: it resolves under the test suite. |
| 3 | **Donors at other hospitals (F1, F2).** A donor code is looked up within the actor's hospital (admins: all) for appointments and for a unit's `donorId`. Another hospital's donor, and an unknown code, both answer 404, so the response reveals neither the donor's name nor the donation interval. Service-level guard as well. | `backend/apps/blood/serializers.py`, `backend/apps/blood/views.py`, `backend/apps/blood/services.py`, `backend/apps/blood/tests/test_donor_scope.py` (new) | Blood bank user at Seaview cannot book a donor from CityCare (404, no appointment, no `donorName` in the body); the same for a unit link (404, and no donation-interval message). Admin books and links both. Same-hospital cases still succeed. |
| 4 | **404 not 403 for other hospitals' records (F3).** Donor screening, appointment cancel, unit test and unit action, and bed action look the record up within the actor's hospital before the service runs. The service's 403 stays as a second guard. | `backend/apps/blood/views.py`, `backend/apps/hospitals/views.py`, `backend/apps/blood/tests/test_hospital_scope.py` (new), `backend/apps/blood/tests/test_screening_and_stock.py` (one assertion 403 to 404), `backend/apps/hospitals/tests/test_beds.py` (one assertion 403 to 404) | One test per affected view: another hospital's record gets 404 and the same body as an unknown id, and nothing changes. |
| 5 | **Every endpoint's guard is checked (F10).** The URL walk now also fails when an `AllowAny` view is not on the allowlist (auth csrf, login, logout, signup, public status, health), and the allowlist must match routes that exist. | `backend/apps/accounts/tests/test_permissions.py` | The extended walk over every `/api/` pattern. |
| 6 | **Login and signup throttle (F4, spec Q10).** DRF throttles on login and signup, keyed on the client address. The address comes from `X-Forwarded-For`, trusting only `DJANGO_TRUSTED_PROXY_COUNT` proxies (default 0, which means `REMOTE_ADDR`; Render sets 1). Rates come from `DJANGO_LOGIN_THROTTLE` and `DJANGO_SIGNUP_THROTTLE`. Off in the test suite unless a test turns it on. | `backend/config/settings.py`, `backend/apps/accounts/throttles.py` (new), `backend/apps/accounts/views.py`, `backend/conftest.py`, `backend/apps/accounts/tests/test_throttle.py` (new), `render.yaml`, `backend/.env.example`, `docs/setup/deployment.md` | Limit reached gives 429 and a later address still gets through; with one trusted proxy a spoofed first `X-Forwarded-For` entry does not change the bucket; with none, the header is ignored; rates of nothing disable the limit. |
| 7 | **`seed_demo --hospitals N` (spec seed section).** N of 3 or more (default 3). Hospitals 4 to N are generated, deterministic per seed and index, with unique ward codes and bed labels. Default output and data are unchanged. | `backend/apps/core/management/commands/seed_demo.py`, `backend/apps/core/tests/test_seed_demo_scale.py` (new) | N=10 creates 10 hospitals; the first three have identical data at N=3 and N=10; re-running changes nothing; N below 3 is a `CommandError`; the existing `test_seed_demo.py` passes unedited. |
| 8 | **Search query count does not grow with hospitals.** A test seeds 3 hospitals, measures the candidate query count, then adds hospitals to 10 and measures again against the same `QUERY_BUDGET`. `test_candidates_performance.py` is not edited. | `backend/apps/matching/tests/test_candidates_scale.py` (new) | Query count at 10 hospitals is within the budget and equal to the count at 3. |
| 9 | **Load test script (spec Q1, Q2).** A standard-library script that logs in as the demo nurse, creates one case at that hospital, warms up, then times `GET /api/emergencies/<ref>/candidates/` at concurrency 1 and 5, and prints p50, p95, p99, max, errors and request count. | `scripts/load_test_search.py` (new), `backend/apps/core/tests/test_load_test_script.py` (new) | Percentile arithmetic on known inputs; end-to-end run against Django's live server with a seeded network (SQLite test database). |
| 10 | **Measured run (spec Q2, acceptance).** Local SQLite (no Docker or Postgres on the build machine), `seed_demo --hospitals 50` on a scratch database, gunicorn with one worker as `render.yaml` runs it. Results and method go in `docs/testing/search-load-test.md`. If p95 misses, find the cause in query counts and fix it only if cheap. | `docs/testing/search-load-test.md` (new), code only if the measurement shows a cheap fix | The measured run itself; row counts, commit, database version and the exact command recorded. |
| 11 | **Permission review and what was fixed (spec Permission review).** The audit table (every view and URL module, guard, hospital scope, finding) and the status of each finding. `api-contracts.md` updated for the changed responses. | `docs/testing/security-review.md` (new), `docs/architecture/api-contracts.md` | Doc review against the code; the table is checked against the URL walk's count. |
| 12 | **Acceptance.** Tick the met criteria in the approved spec. | `docs/aidlc/inception/2026-11-18-security-performance.md` | None; checks run as in every unit. |
| 13 | **Postgres run (22 Nov; closes unit 10's open item).** The exact unit-10 command on PostgreSQL 16, three runs, plus a same-machine SQLite comparison and the per-search query count. | `docs/testing/search-load-test.md` | None; the script and seed are unchanged. |
| 14 | **Review extended to the routes added since (22 Nov).** The 19 views from #104, #106, #109 and #112 get rows with their guard and scope; the donor rows move to the `donors` module (#104). 66 routes in all, each listed. | `docs/testing/security-review.md` | The two URL walks (`test_permissions.py`, and `test_security.py` from #114) pass on every route. |
| 15 | **Findings closed or linked (22 Nov).** F5 and F7 linked to follow-ups #122 and #123. Decision 4 fixed: a throttled sign-in or sign-up says "Wait a minute", not the 15-minute lockout or "server didn't respond". Decision 2 (proxy count) analysed, with a check for staging. | `docs/testing/security-review.md`, `frontend/src/api/auth.ts` | `frontend/src/api/auth.test.ts`: lockout vs throttle replies, and a throttled sign-up. |

## Sequencing

- Unit 1 before 2: both edit the same settings block, and unit 2 relies on the DEBUG-off test helper from unit 1.
- Unit 5 comes before unit 6, so the walk test is in place when the throttle views get their guard, and it checks them too.
- Units 3 and 4 share `apps/blood/views.py`; unit 4 follows unit 3.
- Units 7 and 8 both use `seed_demo`; unit 8 needs the `--hospitals` option from unit 7.
- Unit 9 before 10: the measured run uses the script from unit 9.
- Unit 11 after the code units, so the table describes the code as it ships.
- Unit 12 last.
- Units 13 to 15 were added on 22 Nov, after the bolt's PR (#108) merged, to finish the spec's open criteria that
  don't need staging.

No database migrations are planned. The role table in `apps/accounts/permissions.py` and
`frontend/src/features/staff/roles.ts` does not change (spec, acceptance criteria).

## Test plan

Automated, per unit (pytest, run from `backend/`):

- `ruff check .` and `ruff format --check .`
- `python manage.py makemigrations --check --dry-run` (expected: no changes)
- `python -m pytest -q`: all existing tests pass; the new tests are listed in the table above. No test is
  skipped. The PostgreSQL-only tests run in CI.
- `python3 scripts/check_deploy_config.py` and `python3 scripts/aidlc_board.py --check` from the repository root.
- Deploy check: `DJANGO_DEBUG=false DJANGO_SECRET_KEY=<dummy, 50+ characters> python manage.py check --deploy --fail-level WARNING`
  (also run by CI and by `test_deploy_settings.py`).

Manual, after merge (not done in this bolt, recorded in the operations notes):

- `check --deploy` on the staging service (spec acceptance: "On staging, check --deploy shows no issues").
- Render's health check passes with the SSL redirect on.
- Confirm which headers Vercel and Render add to `X-Forwarded-For` before trusting the count (spec Q10).
- Confirm HSTS passes through Vercel's `/api` proxy (spec Q6), and that `/admin/` answers 404 on staging.

Frontend: no source changes. `frontend/vercel.json` gains one route; `npm run build` is not affected.
The frontend checks are not rerun because no frontend code changes.

Performance: the measured p95 and its method are the deliverable of unit 10. There is no pass or fail gate in
this bolt (spec Q4).

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before
merge. That approval is the Construction gate. The commits are on `krrishna/b13-security-performance`.
