# Security review: permissions and deploy settings (B13)

**Bolt:** [B13](../aidlc/bolts/B13-security-performance.md) · **Issue:** [#58](https://github.com/harishassan-code/hospital-care/issues/58)
**Spec:** [docs/aidlc/inception/2026-11-18-security-performance.md](../aidlc/inception/2026-11-18-security-performance.md)
**Date of review:** 2026-11-18 · **Scope:** every view in `backend/apps/*/views.py`, the three URL modules included from outside
`apps/*/urls.py` (`user_urls`, `hospital_urls`, `case_urls`), `config/urls.py`, and `config/settings.py`.

This is the only security audit in B13. It is not a penetration test, a dependency audit or a WAF review (spec non-goals).

## Method

- Every view was read. "Table" means `module_permission()` in `apps/accounts/permissions.py`. "Helper" means `can_see`,
  `can_edit`, `may_allocate` or `visible_to`, called from a view or service.
- "Scope" means the hospital rule that applies to a record:
  - `own_hospital`: a queryset filter for reads. Another hospital's row is a 404.
  - `changeable_by`: the same filter with admins seeing every row, matching `may_change()`. Used before a write. Another
    hospital's row is a 404 (B13, F3).
  - `may_change`: a check in the service. Refused as 403 in the service, or as 404 where the service raises `Http404`.
- The guard and scope columns below were checked against the code at the end of B13. The URL walk in
  `apps/accounts/tests/test_permissions.py` confirms that every route declares a permission class and that the only
  `AllowAny` routes are the six public ones.
- The `audit`, `notifications` and `resources` apps have no views that answer HTTP requests.

**Defaults.** `DEFAULT_PERMISSION_CLASSES` is `IsAuthenticated`. Every view sets its own class, so the default is not
used. There are no DRF throttle classes except the login and signup limits added in B13 (F4).

**Count.** 47 routes under `/api/`, one view class each: 37 use the table (`module_permission`), 4 use
`IsAuthenticated` with the table helpers (`MeView`, and the three reservation views), and 6 are `AllowAny`: four auth
endpoints, health and public status. The Django admin at `/admin/` is not a DRF view and is listed at the end.

## Review table

| View | Route | Guard | Hospital scope | Finding | After B13 |
|---|---|---|---|---|---|
| CsrfView | GET `/api/auth/csrf/` | AllowAny | none | Public by design, sets cookie | Allowlisted |
| LoginView | POST `/api/auth/login/` | AllowAny | none | Public by design. F4 | Limited per client address (F4) |
| LogoutView | POST `/api/auth/logout/` | AllowAny | none | Public by design | Allowlisted |
| SignupView | POST `/api/auth/signup/` | AllowAny | creates patient accounts only | Public by design. F4 | Limited per client address (F4) |
| MeView | GET `/api/auth/me/` | IsAuthenticated | self | OK | OK |
| UserListView | GET `/api/users/` | table: users | network, admin only | OK | OK |
| UserRoleView | PATCH `/api/users/<id>/` | table: users (edit) | network, admin only | OK, audit-logged | OK |
| BloodUnitListView | GET/POST `/api/blood/units/` | table: blood | own_hospital; POST: donor scoped to the actor (F2) | F2 | Fixed: another hospital's donor is 404 |
| BloodUnitDetailView | GET `/api/blood/units/<id>/` | table: blood | own_hospital | OK | OK |
| BloodUnitTestView | POST `/api/blood/units/<id>/tests/` | table: blood (edit) | changeable_by, 404; then service may_change | F3 | Fixed: 404 |
| BloodUnitActionView | POST `/api/blood/units/<id>/actions/` | table: blood (edit) | changeable_by, 404; then service | F3 | Fixed: 404 |
| BloodStockView | GET `/api/blood/stock/` | table: blood | own_hospital | F9 (GET writes) | Not changed (F9) |
| DonorListView | GET/POST `/api/blood/donors/` | table: blood | own_hospital; POST uses actor's hospital | OK | OK |
| DonorDetailView | GET `/api/blood/donors/<id>/` | table: blood | own_hospital | OK | OK |
| DonorScreeningView | POST `/api/blood/donors/<id>/screening/` | table: blood (edit) | changeable_by, 404; then service | F3 | Fixed: 404 |
| AppointmentListView | GET/POST `/api/blood/appointments/` | table: blood | GET own_hospital; POST: donor scoped to the actor (F1) | F1 | Fixed: another hospital's donor is 404 |
| AppointmentCancelView | POST `/api/blood/appointments/<id>/cancel/` | table: blood (edit) | changeable_by, 404; then service | F3 | Fixed: 404 |
| health | GET `/api/health/` | AllowAny (decorator) | none | Public, Render health check | Allowlisted; exempt from the HTTPS redirect |
| PublicStatusView | GET `/api/public/status/` | AllowAny, no auth classes | none | F5 | Open: decision Q8, follow-up |
| CaseListView | GET/POST `/api/emergencies/` | table: emergencies | own_hospital; POST uses actor's hospital | F9 | Not changed (F9) |
| CaseDetailView | GET `/api/emergencies/<ref>/` | table: emergencies | own_hospital | F9 | Not changed (F9) |
| EmergencyFeedView | GET `/api/emergencies/feed/` | table: emergencies (view) | network-wide by design (#36); no patient field | F9 | Not changed (F9) |
| CaseCandidatesView | GET `/api/emergencies/<ref>/candidates/` | table: emergencies (view) | own_hospital | The search. F9 | Not changed (F9); measured in the load test |
| CaseActionView | POST `/api/emergencies/<ref>/actions/` | table: emergencies (edit) | service apply_case_action may_change (404) | OK | OK |
| CaseReservationsView | POST `/api/emergencies/<ref>/reservations/` | table: emergencies (edit) | own_hospital | OK | OK |
| CaseReservationReleaseView | POST `/api/emergencies/<ref>/reservations/<id>/release/` | table: emergencies (edit) | own_hospital (case) | OK | OK |
| EquipmentListView | GET/POST `/api/equipment/` | table: equipment | own_hospital; POST uses actor's hospital | OK | OK |
| EquipmentActionView | POST `/api/equipment/<id>/actions/` | table: equipment (edit) | service may_change (404) | OK | OK |
| HospitalListView | GET/POST `/api/hospitals/` | table: hospitals (POST admin) | network directory | OK | OK |
| HospitalDetailView | GET/PATCH `/api/hospitals/<id>/` | table: hospitals (PATCH admin) | network | OK | OK |
| CapabilityListView | GET `/api/hospitals/capabilities/` | table: hospitals | none, shared list | OK | OK |
| StructureListView | POST `/api/hospitals/<id>/<kind>/` | table: hospitals (admin) | admin only | OK | OK |
| StructureItemView | DELETE `/api/hospitals/<id>/<kind>/<item>/` | table: hospitals (admin) | admin only | OK | OK |
| BedBoardView | GET `/api/beds/` | table: beds | own_hospital (wards and beds) | OK | OK |
| BedActionView | POST `/api/beds/<label>/actions/` | table: beds (edit) | changeable_by, 404; then service | F3 | Fixed: 404 |
| HeldReservationListView | GET `/api/reservations/` | IsAuthenticated + `can_see` per type | own_hospital | OK, table helper | OK |
| ReservationAllocateView | POST `/api/reservations/<id>/allocate/` | IsAuthenticated + `may_allocate` | own_hospital (404); may_allocate (403) | OK, table helper | OK |
| ReservationAllocateManyView | POST `/api/reservations/allocate/` | IsAuthenticated + `may_allocate` | own_hospital (404); may_allocate (403) | OK, table helper | OK |
| OperatingRoomListView | GET/POST `/api/operating-rooms/` | table: operatingRooms | own_hospital; POST uses actor's hospital | OK | OK |
| OperatingRoomActionView | POST `/api/operating-rooms/<id>/actions/` | table: operatingRooms (edit) | service may_change (404) | OK | OK |
| OperatingRoomScheduleView | GET `/api/operating-rooms/schedule/` | table: operatingRooms | own hospital, in service | OK | OK |
| OrBookingListView | POST `/api/operating-rooms/bookings/` | table: orBookings (edit) | service may_change on the room (404) | OK | OK |
| OrBookingCancelView | POST `/api/operating-rooms/bookings/<id>/cancel/` | table: orBookings (edit) | service may_change (404); surgeons cancel only their own (403) | OK | OK |
| StockView | GET `/api/pharmacy/stock/` | table: pharmacy | none; `Medicine` and `Batch` have no hospital field | F7 | Open: follow-up (F7) |
| TransferListView | GET/POST `/api/transfers/` | table: transfers | GET visible_to; POST own_hospital and service may_change | OK | OK |
| TransferDetailView | GET `/api/transfers/<id>/` | table: transfers | visible_to (404) | OK | OK |
| TransferActionView | POST `/api/transfers/<id>/actions/` | table: transfers (edit) | visible_to (404); may_act per move (403) | OK | OK |
| Django admin (not DRF) | `/admin/` | Django login, `is_staff` | whole site | F6 | Fixed: routed only when `DJANGO_ADMIN_ENABLED=true` (or DEBUG on) |

## Findings

- **F1 (medium), fixed.** `AppointmentSerializer.donorId` looked donors up across every hospital, and `book_appointment`
  never checked the donor's hospital. Now the lookup is limited to the actor's hospital (admins: all), and another
  hospital's donor is a 404 with the same body as an unknown code. The service checks again. Tests:
  `apps/blood/tests/test_donor_scope.py`.
- **F2 (medium), fixed.** A unit's `donorId` had the same wide lookup. Linking a unit to another hospital's donor was
  possible, and the interval error revealed that the donor had given blood recently. Same fix, with no interval message
  in the reply. Tests: `apps/blood/tests/test_donor_scope.py`.
- **F3 (low), fixed.** Donor screening, appointment cancel, unit test and unit action, and bed action looked the record
  up across all hospitals, then the service answered 403, which showed the record exists. Each now looks the record up
  within `changeable_by` first. The service's 403 remains as a second guard. Tests: `apps/blood/tests/test_hospital_scope.py`,
  and the bed case in `apps/hospitals/tests/test_beds.py`.
- **F4 (medium), fixed.** Login and signup had no per-address limit, and the login lockout is per account. Now both have a
  DRF throttle keyed on the client address. The address comes from `X-Forwarded-For` only as far as the trusted proxies
  (`DJANGO_TRUSTED_PROXY_COUNT`) recorded it, and otherwise from `REMOTE_ADDR`. Defaults: login 30 per minute, signup 30
  per hour, both set in the environment. The per-account lockout is unchanged. Tests:
  `apps/accounts/tests/test_throttle.py`.
- **F5 (low), open: decision Q8.** `/api/public/status/` needs no sign-in and returns the on-shift doctors' names,
  departments and shift times. The demo data is synthetic, so the names stay for now. A follow-up is needed before any
  real hospital joins, because staff names on a public page need the staff's consent. The follow-up issue is not filed
  yet and needs the Product Owner.
- **F6 (decision Q7), fixed.** The Django admin at `/admin/` was routed on staging, and the demo `admin@` superuser's
  password is public in `docs/setup/deployment.md`. Now `/admin/` is routed only when `DJANGO_ADMIN_ENABLED=true`, which
  defaults to on under DEBUG and off otherwise. Render sets it to `false`. Tests: `apps/core/tests/test_admin_route.py`.
- **F7 (info), open: follow-up.** Pharmacy stock has no hospital scope, because `Medicine` and `Batch` have no hospital
  field. The catalogue is network-wide for anyone who can view pharmacy. Left unchanged, pending confirmation that this
  is intended (Q9). The follow-up issue is not filed yet.
- **F8 (low), fixed.** With DEBUG off and no `DJANGO_SECRET_KEY`, the app started with the key from the code. Now it
  refuses to start, and the error names the variable. Tests: `apps/core/tests/test_deploy_settings.py`.
- **F9 (info), not changed.** Some GET requests write: the case list, detail and candidates, the reservation and
  transfer reads (`release_expired`, `escalate_overdue`), and blood stock (`expire_overdue_units`). The search's latency
  includes these sweeps, and the load test measures them as they are.
- **F10 (low), fixed.** Nothing enforced the table. `apps/accounts/tests/test_permissions.py` now fails when a route has
  no permission class, or when an `AllowAny` route is not on the allowlist, and when the allowlist names a route that
  is not `AllowAny`.

## Deploy settings (B13, unit 1)

With `DJANGO_DEBUG=false`, `check --deploy --fail-level WARNING` is clean with a 50-character key. It was not before
(W004 and W008). Changes:

- HTTPS redirect on, with `/api/health/` exempt. HSTS on, 3600 seconds by default (`DJANGO_HSTS_SECONDS`), with
  `includeSubDomains`. Preload is not set.
- The Vercel domain sends the same HSTS header (`frontend/vercel.json`). See the decisions below.
- W021 (preload) is silenced in code, on purpose. The header omits the preload token, which is a commitment to the
  browser preload list and out of scope for B13.
- CI runs the same command with a dummy key.

## Decisions and deviations for the Product Owner

1. **HSTS on the Vercel domain.** Spec Q6 says to add the header to `frontend/vercel.json`. The spec's non-goals say no
   HSTS on any host other than the API. The Q6 answer was followed, because users reach only the Vercel domain. The
   `includeSubDomains` token applies to subdomains of the Vercel project domain. Confirm this is wanted, or drop
   `includeSubDomains` from that header.
2. **Proxy count for F4.** `DJANGO_TRUSTED_PROXY_COUNT` is 1 on Render, from the one proxy in front of the app. Staging
   users reach the app through Vercel's `/api` proxy, which may add a second hop. That is not verified. With the wrong
   count, every user behind a proxy shares one bucket. Check the throttle on staging before relying on it.
3. **Throttle rates.** The defaults are 30 per minute for login and 30 per hour for signup, per address. A hospital's
   computers often share one address (the per-account lockout exists for that reason), so a stricter rate would lock out
   a ward.
4. **Frontend copy for a throttled login.** `frontend/src/api/auth.ts` maps every 429 to the lockout message, "Wait 15
   minutes". A throttled request waits about a minute. The copy is not changed in B13, since the spec scopes F4 to the
   backend. Follow-up.
5. **Silenced W021.** See above. The spec's acceptance line "prints no issues" holds with one check silenced on purpose.

## Follow-ups (not done in B13)

- **Staging checks (after merge, recorded in the operations notes):** `check --deploy` on the staging service
  (spec acceptance); `/api/health/` passes Render's check with the HTTPS redirect on; `/admin/` answers 404 on
  staging; HSTS arrives through Vercel's `/api` proxy and on the Vercel domain; `DJANGO_TRUSTED_PROXY_COUNT` gives
  each user its own sign-in bucket (decision 2).
- **Postgres run of the load test.** `docs/testing/search-load-test.md` records SQLite only. Run the same command on
  Postgres 17 before the B15 report (spec Q2).
- **Follow-up issues to file (not filed here):** F5 (public staff names, before any real hospital joins); F7 (pharmacy
  has no hospital scope, unless the Product Owner confirms it is intended); the frontend copy for a throttled sign-in
  (decision 4).
- **Decisions for the Product Owner:** decision 1 (the Vercel `includeSubDomains` header, which the spec's non-goals
  do not allow for hosts other than the API); decision 3 (the throttle rates); and when to raise HSTS to one year
  (spec Q6 says after a week of HTTPS-only staging).
- **Not changed, by design:** the GET-time sweeps (F9) and the demo logins, which stay public for the demo (spec
  non-goals).
