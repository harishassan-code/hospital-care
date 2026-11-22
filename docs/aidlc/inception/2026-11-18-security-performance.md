# Inception Spec: Security and performance hardening

**Date:** 2026-11-18
**Author:** Claude, drafted for review (branch owner: Krrishna)
**Related backlog item:** [#58](https://github.com/harishassan-code/hospital-care/issues/58) Security and performance hardening (bolt [B13](../bolts/B13-security-performance.md), Sprint 9)

## Problem

Staging is public and is the site the team demos, but three things are not yet shown to be safe or fast:

1. **Deployment settings.** With `DJANGO_DEBUG=false`, `manage.py check --deploy` still warns that HSTS is not set (W004) and that the SSL redirect is off (W008). Secure session and CSRF cookies are already on. If `DJANGO_SECRET_KEY` is missing, the server starts with the key from the code (W009). These results come from a local run with a dummy key. Staging itself has not been checked from this repo.
2. **Access control.** Every API view declares a guard. 40 of the 47 check the role table in `apps/accounts/permissions.py` (37 through `module_permission`, 3 through helpers). The hospital rule is applied mostly in the service layer, and two write paths skip it. A blood bank user can book a donor registered at another hospital and see that donor's name. Some views answer 403 rather than 404 for another hospital's record, which reveals that the record exists.
3. **Speed at city size.** The candidate search is tested only on the three-hospital demo network, in-process, with a one-second budget and a query-count cap. Nobody has timed it over HTTP on a network the size of a city, so the final report has no number.

This is for:

- **Admin**, who runs staging, and the Product Owner, who decides it is safe to show.
- **Blood bank** staff, whose donor records must stay with the hospital that registered them.
- **Doctors and nurses** (emergency coordinators), who run the candidate search while a case is open.

## User stories

- As the admin who runs staging, I want the deployment checks to pass with HTTPS enforced, so that sign-in cookies and patient data are never sent over plain HTTP. (#58)
- As the admin, I want every API endpoint's role rule and hospital scope written down and tested, so that no staff member can reach another hospital's stock, donors or cases. (#58)
- As a blood bank user, I want donors registered at another hospital kept out of my appointments and blood units, so that donor details stay with the hospital that registered them.
- As a doctor or nurse, I want the candidate search to stay quick on a network the size of the city, so that matches come up while the case is still open.
- As the team, we want a repeatable load test on seeded city-sized data, so that the final report carries a measured p95 and the staging demo data stays as it is. (#58)

## Acceptance criteria

The bolt's two criteria are kept and refined below.

### Deployment checks (bolt: `check --deploy` clean on staging)

- [x] With `DJANGO_DEBUG=false` and a random `DJANGO_SECRET_KEY` of 50 characters or more, `python manage.py check --deploy --fail-level WARNING` prints no issues and exits 0. Today it prints W004 and W008.
- [x] With `DJANGO_DEBUG=false` and no `DJANGO_SECRET_KEY`, the server refuses to start, and the error names the variable. Today it starts with the key from the code.
- [x] HSTS and the SSL redirect are on only when DEBUG is off. The HSTS length comes from `DJANGO_HSTS_SECONDS`. Local development and the test suite (DEBUG on by default) behave as before.
- [x] `/api/health/` is exempt from the SSL redirect, so Render's health check still passes.
- [x] CI runs the same `check --deploy` command with a dummy key, so a regression fails the build.
- [ ] On staging, `check --deploy` shows no issues. The output is recorded in the operations notes.

### Permission review (bolt: permission review notes)

- [x] Every view in `apps/*/views.py` and every URL module appears in the review table in the Design section, with its guard and hospital scope. Each finding is fixed in this bolt or linked to a follow-up issue.
- [x] A donor registered at another hospital is refused for an appointment (F1) and for a blood unit link (F2), with a 404 and a test for each. Admins, who see the whole network, can still do both.
- [x] Views that look up a record before the service check return 404 for another hospital's record, not 403 (F3). Each affected view has a test.
- [x] A test walks every `/api/` URL pattern and fails if a view declares no permission class, or is `AllowAny` but not on the allowlist: the auth csrf, login, logout and signup endpoints, the public status endpoint and health (F10).
- [x] The role table (`ACCESS` in `apps/accounts/permissions.py` and `frontend/src/features/staff/roles.ts`) does not change in this bolt unless the Product Owner approves a change.

### Search performance (bolt: search p95 recorded)

- [x] `seed_demo --hospitals N` seeds N hospitals, where N is 3 or more. With no flag, the data and output are unchanged, and the existing tests pass without edits.
- [x] `scripts/load_test_search.py` times `GET /api/emergencies/<reference>/candidates/` over HTTP, on Postgres, against a seeded network of 50 hospitals (proposed, Q3), after a warm-up. It reports p50, p95, p99, max and the error count, at concurrency 1 and 5 (proposed).
- [x] The p95 is recorded in `docs/testing/search-load-test.md` with the dataset's row counts, the commit, the database version and the exact command. The final report (B15) links to it.
- [x] A test shows the candidate query count does not grow with the number of hospitals: the same `QUERY_BUDGET` holds at 10 hospitals as at 3.
- [x] `apps/matching/tests/test_candidates_performance.py` passes unchanged.

## Design

### Settings (`backend/config/settings.py`)

Every new value comes from the environment or sits inside the existing `if not DEBUG:` block. Local development and tests, which run with DEBUG on, see no change.

```python
if not DEBUG:  # extends the existing block
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^api/health/$"]  # Render's health check, so it isn't redirected
    SECURE_HSTS_SECONDS = positive_int_env("DJANGO_HSTS_SECONDS", 3600)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
```

- `SECRET_KEY`: keep the dev default only when DEBUG is on. When DEBUG is off and `DJANGO_SECRET_KEY` is unset, raise `ImproperlyConfigured`, the same way `positive_int_env` refuses a bad value.
- Already right, no change: secure session and CSRF cookies when DEBUG is off, `SECURE_PROXY_SSL_HEADER`, and Django's defaults for `X_FRAME_OPTIONS` (DENY) and `SECURE_CONTENT_TYPE_NOSNIFF`.
- HSTS applies to the host that sends it and that host's subdomains. The API host is `hospital-care-api.onrender.com`, so `includeSubDomains` covers nothing else.

Deploy check results (DEBUG off, dummy key, run from this worktree):

| Check | Today | After this bolt |
|---|---|---|
| W004 HSTS not set | warns | HSTS set, 3600 s on the first deploy |
| W005 includeSubDomains | not reached yet; appears as soon as HSTS is set without it | set |
| W008 SSL redirect off | warns | on, health path exempt |
| W009 key from code (only when `DJANGO_SECRET_KEY` is unset) | warns | server refuses to start |

The SSL redirect has one risk: if Render's health check arrives over plain HTTP, the redirect fails it. The exemption avoids that. Confirm on the first staging deploy.

### Permission review

**Method.** Every `views.py` and every URL module was read. That includes the three modules `config/urls.py` includes from outside `apps/*/urls.py`: `user_urls`, `hospital_urls` and `case_urls`. "Table" means `module_permission()` in `apps/accounts/permissions.py`. "Helper" means `can_see`, `can_edit` or `may_allocate` called from a view or service. "Scope" means `own_hospital` (a queryset filter, so another hospital's row is a 404) or `may_change` (a check in the service). The `audit`, `notifications` and `resources` apps have no views yet.

**Defaults.** `DEFAULT_PERMISSION_CLASSES` is `IsAuthenticated`, a safe default. Every view sets its own class, so the default is not used. There are no DRF throttle classes.

**Count.** 47 views. 37 use the table directly. 3 matching views use `IsAuthenticated` with table helpers. `MeView` uses `IsAuthenticated`. 6 are `AllowAny`: four auth endpoints, health and public status.

| View | Route | Guard | Hospital scope | Finding |
|---|---|---|---|---|
| CsrfView | GET `/api/auth/csrf/` | AllowAny | none | Public by design, sets cookie |
| LoginView | POST `/api/auth/login/` | AllowAny | none | Public by design. F4 |
| LogoutView | POST `/api/auth/logout/` | AllowAny | none | Public by design |
| SignupView | POST `/api/auth/signup/` | AllowAny | creates patient accounts only | Public by design. F4 |
| MeView | GET `/api/auth/me/` | IsAuthenticated | self | OK |
| UserListView | GET `/api/users/` | table: users | network, admin only | OK |
| UserRoleView | PATCH `/api/users/<id>/` | table: users (edit) | network, admin only | OK, audit-logged |
| BloodUnitListView | GET/POST `/api/blood/units/` | table: blood | own_hospital; POST uses actor's hospital | F2 (POST `donorId`) |
| BloodUnitDetailView | GET `/api/blood/units/<id>/` | table: blood | own_hospital | OK |
| BloodUnitTestView | POST `/api/blood/units/<id>/tests/` | table: blood (edit) | global lookup, then `_locked_unit` may_change (403) | F3 |
| BloodUnitActionView | POST `/api/blood/units/<id>/actions/` | table: blood (edit) | global lookup, then `_locked_unit` (403) | F3 |
| BloodStockView | GET `/api/blood/stock/` | table: blood | own_hospital | F9 (GET writes) |
| DonorListView | GET/POST `/api/blood/donors/` | table: blood | own_hospital; POST uses actor's hospital | OK |
| DonorDetailView | GET `/api/blood/donors/<id>/` | table: blood | own_hospital | OK |
| DonorScreeningView | POST `/api/blood/donors/<id>/screening/` | table: blood (edit) | global lookup, then `screen_donor` may_change (403) | F3 |
| AppointmentListView | GET/POST `/api/blood/appointments/` | table: blood | GET own_hospital; POST never checks the donor's hospital | F1 |
| AppointmentCancelView | POST `/api/blood/appointments/<id>/cancel/` | table: blood (edit) | global lookup, then service may_change (403) | F3 |
| health | GET `/api/health/` | AllowAny (decorator) | none | Public, Render health check |
| PublicStatusView | GET `/api/public/status/` | AllowAny, no auth classes | none | F5 |
| CaseListView | GET/POST `/api/emergencies/` | table: emergencies | own_hospital; POST uses actor's hospital | F9 |
| CaseDetailView | GET `/api/emergencies/<ref>/` | table: emergencies | own_hospital | F9 |
| EmergencyFeedView | GET `/api/emergencies/feed/` | table: emergencies (view) | network-wide by design (#36); no patient field | F9 |
| CaseCandidatesView | GET `/api/emergencies/<ref>/candidates/` | table: emergencies (view) | own_hospital | The search. F9 |
| CaseActionView | POST `/api/emergencies/<ref>/actions/` | table: emergencies (edit) | service `apply_case_action` may_change (404) | OK |
| CaseReservationsView | POST `/api/emergencies/<ref>/reservations/` | table: emergencies (edit) | own_hospital | OK |
| CaseReservationReleaseView | POST `/api/emergencies/<ref>/reservations/<id>/release/` | table: emergencies (edit) | own_hospital (case) | OK |
| EquipmentListView | GET/POST `/api/equipment/` | table: equipment | own_hospital; POST uses actor's hospital | OK |
| EquipmentActionView | POST `/api/equipment/<id>/actions/` | table: equipment (edit) | service may_change (404) | OK |
| HospitalListView | GET/POST `/api/hospitals/` | table: hospitals (POST admin) | network directory | OK |
| HospitalDetailView | GET/PATCH `/api/hospitals/<id>/` | table: hospitals (PATCH admin) | network | OK |
| CapabilityListView | GET `/api/hospitals/capabilities/` | table: hospitals | none, shared list | OK |
| StructureListView | POST `/api/hospitals/<id>/<kind>/` | table: hospitals (admin) | admin only | OK |
| StructureItemView | DELETE `/api/hospitals/<id>/<kind>/<item>/` | table: hospitals (admin) | admin only | OK |
| BedBoardView | GET `/api/beds/` | table: beds | own_hospital (wards and beds) | OK |
| BedActionView | POST `/api/beds/<label>/actions/` | table: beds (edit) | global lookup, then service may_change (403) | F3 |
| HeldReservationListView | GET `/api/reservations/` | IsAuthenticated + `can_see` per type | own_hospital | OK, table helper |
| ReservationAllocateView | POST `/api/reservations/<id>/allocate/` | IsAuthenticated + `may_allocate` | own_hospital (404); may_allocate (403) | OK, table helper |
| ReservationAllocateManyView | POST `/api/reservations/allocate/` | IsAuthenticated + `may_allocate` | own_hospital (404); may_allocate (403) | OK, table helper |
| OperatingRoomListView | GET/POST `/api/operating-rooms/` | table: operatingRooms | own_hospital; POST uses actor's hospital | OK |
| OperatingRoomActionView | POST `/api/operating-rooms/<id>/actions/` | table: operatingRooms (edit) | service may_change (404) | OK |
| OperatingRoomScheduleView | GET `/api/operating-rooms/schedule/` | table: operatingRooms | own hospital, in service | OK |
| OrBookingListView | POST `/api/operating-rooms/bookings/` | table: orBookings (edit) | service may_change on the room | OK |
| OrBookingCancelView | POST `/api/operating-rooms/bookings/<id>/cancel/` | table: orBookings (edit) | service may_change; surgeons cancel only their own | OK |
| StockView | GET `/api/pharmacy/stock/` | table: pharmacy | none; `Medicine` and `Batch` have no hospital field | F7 |
| TransferListView | GET/POST `/api/transfers/` | table: transfers | GET visible_to; POST own_hospital and service may_change | OK |
| TransferDetailView | GET `/api/transfers/<id>/` | table: transfers | visible_to (404) | OK |
| TransferActionView | POST `/api/transfers/<id>/actions/` | table: transfers (edit) | visible_to (404); may_act per move (403) | OK |
| Django admin (not DRF) | `/admin/` | Django login, `is_staff` | whole site | F6 |

**Findings**

- **F1 (medium).** `AppointmentSerializer.donorId` looks donors up across every hospital, and `book_appointment` never checks the donor's hospital. A blood bank user can book a donor from another hospital, and the reply includes `donorName`. Fix: scope the lookup to the actor's hospital (admins: all), with a 404 otherwise.
- **F2 (medium).** The unit create serializer's `donorId` (`apps/blood/serializers.py`, around line 52) has the same wide lookup, so a unit can be linked to another hospital's donor. The donation-interval error then reveals that the donor gave blood recently. Same fix.
- **F3 (low).** Donor screening, appointment cancel, unit test and action, and bed action fetch the row with a global lookup, then the service answers 403. The 403 shows the record exists. Fix: scope the lookup with `own_hospital`, as the other views do.
- **F4 (medium).** No per-IP limit on login or signup, and DRF has no throttle classes. The login lockout (5 failures, 15 minutes) is keyed by email and kept in the default process-local cache, since no `CACHES` is set. It resets on restart and counts per worker.
- **F5 (low, decision).** `/api/public/status/` needs no sign-in and returns each on-shift doctor's name, department and shift times. See Q8.
- **F6 (decision).** The Django admin at `/admin/` sits outside DRF and the table. The demo `admin@` account is a superuser, and its password is printed in `docs/setup/deployment.md`, so anyone who reads that doc can open `/admin/` on staging. See Q7.
- **F7 (info).** Pharmacy stock has no hospital scope. `Medicine` and `Batch` have no hospital field, so the catalogue is network-wide for anyone who can view pharmacy. Confirm this is intended.
- **F8 (low).** With DEBUG off and no `DJANGO_SECRET_KEY`, the app starts with the key from the code (W009). `render.yaml` generates the key (`generateValue`), so only a misconfigured host is exposed. Fix: refuse to start (see Settings).
- **F9 (info).** Some GET requests write: the case list, detail and candidates, and the reservations and transfers endpoints (`release_expired`, `escalate_overdue`), plus blood stock (`expire_overdue_units`). Search latency includes these sweeps, so the load test measures them. No change in this bolt.
- **F10 (low).** Nothing enforces the table. The default permission is `IsAuthenticated`, which is safe, but no test checks that each view declares a guard. Fix: the URL-walk test in the acceptance criteria.

### seed_demo `--hospitals N`

- The option is `--hospitals N`, default 3, and below 3 is a `CommandError`. The three named hospitals always come first with their current data, because the tests and the demo script use "Seaview Hospital" and "CityCare General Hospital".
- Hospitals 4 to N are generated: "Synthetic Hospital 04" onward, address "Karachi (synthetic)", coordinates drawn from a seeded random box around the city centre, and wards and departments from a generic template. Generated names must not match a real hospital (AGENTS.md data rule).
- Each generated hospital gets its own seeded random stream, as the existing loop already does (`seed * 100 + index`). Adding hospitals changes no existing hospital's data.
- Re-runs are safe. `seed_hospital` uses `get_or_create`, and the stock and room seeders check each hospital first. Construction must confirm that `seed_or_bookings` has the same guard, since `handle()` calls it for every hospital without one.
- The Render build keeps the default (3), so staging is unchanged. `--reset` already wipes every hospital.

### Load test

- **Tool:** a standard-library script, `scripts/load_test_search.py` (see Q1).
- **Setup:** local Postgres 17 from `docker-compose.yml`, seeded with `seed_demo --hospitals 50`. The script creates one case through the API at the nurse's hospital, with the four needs used in `test_candidates_performance.py`. It then signs in as the demo nurse, runs warm-up requests and times `GET` requests to the candidates endpoint.
- **Realism:** each timed request is a plain `GET`, so the search's own release sweep (F9) runs every time, as it does in production.
- **Output:** p50, p95, p99, max, error count, request count and concurrency. Each run is one row in `docs/testing/search-load-test.md` (next to `docs/testing/results/`), with the date, commit, N, row counts for hospitals, beds, blood units, equipment and rooms, the Postgres version and the command.
- **Gate:** none in this bolt (Q4). The in-process budget test stays as the regression guard.
- **Sending requests:** for HTTPS targets, the script sends the `Origin` and `Referer` headers Django's CSRF check expects.

## Non-goals

- New features, new roles, or changes to the role table. Those are Product Owner decisions.
- A penetration test, a dependency audit, a WAF or DDoS protection. The review above is the only security audit in this bolt.
- Caching or query rewrites. Performance work starts only if a measured p95 misses a target set later. This bolt records the number.
- Locust, distributed or soak tests, and any load test against staging.
- HSTS preload, or HSTS on any host other than the API.
- Moving the GET-time sweeps out of read requests (F9). They are measured, not changed.
- Changing the demo logins themselves (Q7 covers the Django admin route).

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Load-test tool: Locust or a Python timing script?** *Proposed:* a Python timing script that uses only the standard library (`urllib`, `http.cookiejar`, `concurrent.futures`), in `scripts/load_test_search.py`. It adds no dependency (`requirements.txt` has none), it measures one endpoint with one number, and its output is a plain table. Locust is the better tool if we later need ramp-up, many simulated users or a live dashboard. httpx would also work, but it adds a dependency with no gain here.
2. **Where the load test runs.** *Proposed:* local Postgres 17 from `docker-compose.yml`, seeded with `seed_demo --hospitals 50`, never staging. Staging is shared, sleeps after 15 minutes, takes 30 to 60 seconds to wake, and seeding it would change the demo network. One warm request on staging can be recorded as a smoke check, labelled as not comparable.
3. **What "city-sized" means.** *Proposed:* 50 hospitals, with the row counts recorded alongside the result. The Product Owner can change the number. The flag makes it a parameter.
4. **Pass or fail on p95.** *Proposed:* record only, in this bolt. The one-second in-process budget stays as the regression guard. Set a target after the first measured run, not before it.
5. **Where `check --deploy` is enforced.** *Proposed:* in CI, with a dummy key of 50+ characters, so a regression fails the build. Plus one run on the staging service, recorded in the operations notes. Adding it to the `render.yaml` build command would also block deploys on a config mistake. That is a choice for the Product Owner.
6. **HSTS values.** *Proposed:* `DJANGO_HSTS_SECONDS` defaults to 3600 for the first deploy, then goes to 31536000 (one year) after a week of HTTPS-only staging, since browsers cache HSTS and it is hard to undo. `includeSubDomains` on, which W005 requires, and it covers nothing but the API host. No preload. Users reach only the Vercel domain, so add the same header to `frontend/vercel.json`. Whether Render's header passes through Vercel's `/api` proxy is not verified.
7. **Demo logins and the Django admin on staging.** *Proposed:* keep the public demo logins, since the demo needs them. Route `/admin/` only when `DJANGO_ADMIN_ENABLED=true`, which defaults to off when DEBUG is off, so staging can opt in.
8. **Public doctor names (F5).** *Proposed:* leave the names as they are in this bolt, since the demo data is synthetic. Raise a follow-up before any real hospital joins, because staff names on a public page need the staff's consent.
9. **Fix the cross-hospital paths here, or file them?** *Proposed:* fix F1, F2, F3 and F10 in this bolt. Each is a scope change with a test, and this bolt is security hardening. File F7 as a follow-up issue unless the team confirms it is intended.
10. **Login and signup throttling (F4).** *Proposed:* add DRF throttles to login and signup in this bolt. Key them on the client IP taken from `X-Forwarded-For`, trusted only from the known proxies, not on `REMOTE_ADDR`. Behind a proxy, `REMOTE_ADDR` is the proxy's address, so a naive limit would lock everyone out together. Confirm which header carries the real client through Vercel and Render (not verified). The default cache is per process, which is fine while gunicorn runs one worker (`render.yaml` sets no `-w`). Note it if the worker count goes up.

## Approval

- [x] Approved by: Krrishna on 2026-11-18 (proposed answers accepted as written)
