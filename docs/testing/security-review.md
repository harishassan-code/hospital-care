# Security review: permissions and deploy settings (B13)

**Bolt:** [B13](../aidlc/bolts/B13-security-performance.md) · **Issue:** [#58](https://github.com/harishassan-code/hospital-care/issues/58)
**Spec:** [docs/aidlc/inception/2026-11-18-security-performance.md](../aidlc/inception/2026-11-18-security-performance.md)
**Date of review:** 2026-11-18, extended 2026-11-22 to the routes added since (#104, #106, #109, #112) · **Scope:** every
view in `backend/apps/*/views.py` and `*_views.py`, the URL modules included from outside `apps/*/urls.py`
(`user_urls`, `hospital_urls`, `case_urls`, `trip_urls`, `patient_transfer_urls`), `config/urls.py`, and
`config/settings.py`.

This is the only security audit in B13. It is not a penetration test, a dependency audit or a WAF review (spec non-goals).

## Method

- Every view was read. "Table" means `module_permission()` in `apps/accounts/permissions.py`. "Helper" means `can_see`,
  `can_edit`, `may_allocate` or `visible_to`, called from a view or service.
- "Scope" means the hospital rule that applies to a record:
  - `own_hospital`: a queryset filter for reads. Another hospital's row is a 404.
  - `changeable_by`: the same filter with admins seeing every row, matching `may_change()`. Used before a write. Another
    hospital's row is a 404 (B13, F3).
  - `may_change`: a check in the service. Refused as 403 in the service, or as 404 where the service raises `Http404`.
- The guard and scope columns below were checked against the code at the end of B13, and again on 22 Nov for the
  19 routes added since. Two URL walks enforce the guards: `apps/accounts/tests/test_permissions.py` (every route
  declares a permission class, and the only `AllowAny` routes are the six public ones) and
  `apps/core/tests/test_security.py` (#114: no route is open to anyone or checks only sign-in, outside a commented
  allowlist).
- The `resources` app has no views that answer HTTP requests.

**Defaults.** `DEFAULT_PERMISSION_CLASSES` is `IsAuthenticated`. Every view sets its own class, so the default is not
used. There are no DRF throttle classes except the login and signup limits added in B13 (F4).

**Count.** 66 routes under `/api/` (47 at the first review), one view class each: 53 use the table
(`module_permission`), 4 use `IsAuthenticated` with the table helpers (`MeView`, and the three reservation views), 3
use `IsStaff` and touch only the signed-in user's own notifications, and 6 are `AllowAny`: four auth endpoints, health
and public status. The Django admin at `/admin/` is not a DRF view and is listed at the end.

## Review table

| View | Route | Guard | Hospital scope | Finding | After B13 |
|---|---|---|---|---|---|
| CsrfView | GET `/api/auth/csrf/` | AllowAny | none | Public by design, sets cookie | Allowlisted |
| LoginView | POST `/api/auth/login/` | AllowAny | none | Public by design. F4 | Limited per client address (F4) |
| LogoutView | POST `/api/auth/logout/` | AllowAny | none | Public by design | Allowlisted |
| SignupView | POST `/api/auth/signup/` | AllowAny | creates patient accounts only | Public by design. F4 | Limited per client address (F4) |
| MeView | GET `/api/auth/me/` | IsAuthenticated | self | OK | OK |
| UserListView | GET `/api/users/` | table: users | network, admin only | OK | OK |
| UserRoleView | PATCH `/api/users/<id>/` | table: users (edit) | network, admin only | F12 | Fixed: a hospital role needs a hospital; role and hospital set together, audit-logged |
| BloodUnitListView | GET/POST `/api/blood/units/` | table: blood | own_hospital; POST: donor scoped to the actor (F2) | F2 | Fixed: another hospital's donor is 404 |
| BloodUnitDetailView | GET `/api/blood/units/<id>/` | table: blood | own_hospital | OK | OK |
| BloodUnitTestView | POST `/api/blood/units/<id>/tests/` | table: blood (edit) | changeable_by, 404; then service may_change | F3 | Fixed: 404 |
| BloodUnitActionView | POST `/api/blood/units/<id>/actions/` | table: blood (edit) | changeable_by, 404; then service | F3 | Fixed: 404 |
| BloodStockView | GET `/api/blood/stock/` | table: blood | own_hospital | F9 (GET writes) | Not changed (F9) |
| DonorListView | GET/POST `/api/blood/donors/` | table: donors | own_hospital; POST uses actor's hospital | OK | OK |
| DonorDetailView | GET `/api/blood/donors/<id>/` | table: donors | own_hospital | OK | OK |
| DonorScreeningView | POST `/api/blood/donors/<id>/screening/` | table: donors (edit) | changeable_by, 404; then service | F3 | Fixed: 404 |
| AppointmentListView | GET/POST `/api/blood/appointments/` | table: donors | GET own_hospital; POST: donor scoped to the actor (F1) | F1 | Fixed: another hospital's donor is 404 |
| AppointmentCancelView | POST `/api/blood/appointments/<id>/cancel/` | table: donors (edit) | changeable_by, 404; then service | F3 | Fixed: 404 |
| health | GET `/api/health/` | AllowAny (decorator) | none | Public, Render health check | Allowlisted; exempt from the HTTPS redirect |
| PublicStatusView | GET `/api/public/status/` | AllowAny, session read but not required | none | F5 | Fixed (#122): names only for signed-in staff |
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
| StockView | GET `/api/pharmacy/stock/` | table: pharmacy | own_hospital on batches; the formulary is shared | F7 | Fixed (#123): batches per hospital |
| TransferListView | GET/POST `/api/transfers/` | table: transfers | GET visible_to; POST own_hospital and service may_change | OK | OK |
| TransferDetailView | GET `/api/transfers/<id>/` | table: transfers | visible_to (404) | OK | OK |
| TransferActionView | POST `/api/transfers/<id>/actions/` | table: transfers (edit) | visible_to (404); may_act per move (403) | OK | OK |
| CasePatientTransferView | POST `/api/emergencies/<ref>/patient-transfer/` | table: emergencies (edit) | own_hospital case (404); service: edit at the case's hospital (403) | OK (B17, added 22 Nov) | OK |
| PatientTransferListView | GET `/api/patient-transfers/` | table: emergencies | visible_to: the sending or receiving hospital; admins all | OK (B17) | OK |
| PatientTransferActionView | POST `/api/patient-transfers/<id>/actions/` | table: emergencies (edit) | visible_to (404); may_act: arrive at the receiver, cancel at the sender (403) | OK (B17) | OK |
| AmbulanceListView | GET/POST `/api/ambulances/` | table: ambulances | own hospital, admins all; POST at the actor's hospital (admins choose) | OK (B04) | OK |
| AmbulanceActionView | POST `/api/ambulances/<id>/actions/` | table: ambulances (edit) | service may_change (404) | OK (B04) | OK |
| TransferTripView | POST `/api/transfers/<id>/trips/` | table: ambulances (edit) | transfer visible_to (404); service: edit ambulances at the supplier (403); ambulance must be the supplier's (404) | OK (B05) | OK |
| TripActionView | POST `/api/trips/<id>/actions/` | table: ambulances (edit) | trip's transfer visible_to (404); service: may step at the supplier (403) | OK (B05) | OK |
| CommandCentreView | GET `/api/command-centre/` | table: commandCentre (admin only) | network-wide by design (#55) | OK (B09) | OK |
| AuditEntryListView | GET `/api/audit/entries/` | table: audit (admin only) | network; writes answer 405 for everyone | OK (B10) | OK |
| AuditExportView | GET `/api/audit/entries/export/` | table: audit (admin only) | network; capped at 10,000 rows; cells that look like formulas escaped; the export is audit-logged | OK (B10) | OK |
| ReportView | GET `/api/reports/` | table: reports (admin only) | network, or one hospital by filter; writes 405 | OK (B18) | OK |
| ReportExportView | GET `/api/reports/export/` | table: reports (admin only) | as ReportView; formula cells escaped; audit-logged as `report.exported` | OK (B18) | OK |
| NotificationListView | GET `/api/notifications/` | IsStaff | the signed-in user's own rows only | OK (B06) | OK |
| NotificationUnreadCountView | GET `/api/notifications/unread-count/` | IsStaff | own rows only | OK (B06) | OK |
| NotificationReadView | POST `/api/notifications/<id>/read/` | IsStaff | own rows; another user's is 404; audit-logged | OK (B06) | OK |
| SpecialistListView | GET/POST `/api/specialists/` | table: specialists | reads network-wide by design (B16 spec); POST at the actor's hospital, admins any (403) | OK (B16) | OK |
| SpecialistDetailView | GET/PATCH `/api/specialists/<id>/` | table: specialists | reads network-wide; PATCH own hospital, admins any (403). A 403, not a 404, reveals nothing: the record is readable | OK (B16) | OK |
| OnCallWindowListView | POST `/api/specialists/<id>/on-call/` | table: specialists (edit) | own hospital, admins any (403); overlaps refused (400) | OK (B16) | OK |
| OnCallWindowDetailView | DELETE `/api/specialists/<id>/on-call/<window>/` | table: specialists (edit) | own hospital, admins any (403); only windows that haven't started (409) | OK (B16) | OK |
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
  and the bed case in `apps/accounts/tests/test_permissions.py` (`TestOwnHospitalOnly`).
- **F4 (medium), fixed.** Login and signup had no per-address limit, and the login lockout is per account. Now both have a
  DRF throttle keyed on the client address. The address comes from `X-Forwarded-For` only as far as the trusted proxies
  (`DJANGO_TRUSTED_PROXY_COUNT`) recorded it, and otherwise from `REMOTE_ADDR`. Defaults: login 30 per minute, signup 30
  per hour, both set in the environment. The per-account lockout is unchanged. Tests:
  `apps/accounts/tests/test_throttle.py`.
- **F5 (low), fixed (23 Nov, #122).** `/api/public/status/` needs no sign-in and returned the on-shift doctors' names,
  departments and shift times. Staff names on a public page need the staff's consent, and CityCare is meant for any
  hospital that joins. Now the public sees each shift's department and hours with `name: null`; signed-in hospital
  staff (who can already see the staff directory) see the names. The view reads the session to tell them apart and
  still requires nothing. Tests in `apps/emergencies/tests/test_public_status.py`.
- **F6 (decision Q7), fixed.** The Django admin at `/admin/` was routed on staging, and the demo `admin@` superuser's
  password is public in `docs/setup/deployment.md`. Now `/admin/` is routed only when `DJANGO_ADMIN_ENABLED=true`, which
  defaults to on under DEBUG and off otherwise. Render sets it to `false`. Tests: `apps/core/tests/test_admin_route.py`.
- **F7 (info), fixed (23 Nov, #123).** Pharmacy stock had no hospital scope, because `Medicine` and `Batch` had no
  hospital field, so anyone who could view pharmacy saw the whole network's batches. Now each `Batch` belongs to a
  hospital and the stock view filters batches with `own_hospital`; the medicine list (the formulary) stays shared.
  Migration `pharmacy/0002` gives batches from before the change to the first hospital registered (the one the
  system then served), and `seed_demo` gives every hospital its own stock. Tests in `apps/pharmacy/tests/test_stock.py`.
- **F8 (low), fixed.** With DEBUG off and no `DJANGO_SECRET_KEY`, the app started with the key from the code. Now it
  refuses to start, and the error names the variable. Tests: `apps/core/tests/test_deploy_settings.py`.
- **F9 (info), not changed.** Some GET requests write: the case list, detail and candidates, the reservation and
  transfer reads (`release_expired`, `escalate_overdue`), and blood stock (`expire_overdue_units`). The search's latency
  includes these sweeps, and the load test measures them as they are.
- **F10 (low), fixed.** Nothing enforced the table. `apps/accounts/tests/test_permissions.py` now fails when a route has
  no permission class, or when an `AllowAny` route is not on the allowlist, and when the allowlist names a route that
  is not `AllowAny`.

Found on 22 Nov by the [functional sweep](functional-sweep.md), which drove every page and form as each role:

- **F11 (medium), fixed.** `own_hospital()` gave the whole network to *any* user without a hospital, not only to
  admins. A patient promoted to nurse on the Users page has no hospital, so they read every hospital's beds, blood,
  cases and stock. Writes were safe (`changeable_by()` already limited them). Now a non-admin without a hospital sees
  only rows with no hospital, as `changeable_by()` does. Test: `test_staff_without_a_hospital_no_longer_see_every_hospitals_rows`.
- **F12 (medium), fixed.** There was no way to give a user a hospital: `PATCH /api/users/<id>/` took only a role, and
  the Django admin is off on staging (F6). So the only way to add staff on staging made the F11 account above. The
  endpoint now takes `hospitalId`, refuses a doctor, nurse, blood bank or pharmacist without one, and logs both
  changes; the Users page has a hospital picker beside the role. Tests in `apps/accounts/tests/test_roles.py` and
  `UsersPage.test.tsx`.

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
   users reach the app through Vercel's `/api` proxy, a second hop. Vercel sets `X-Forwarded-For` to the visitor's
   address and Render's proxy appends Vercel's, so the app sees `<visitor>, <vercel>`. With the count at 1,
   `client_address()` takes the last entry: every site user shares Vercel's address, and so one sign-in bucket of 30
   a minute. With the count at 2 each visitor gets their own bucket, but a caller who skips Vercel and calls the
   Render URL directly can write the first entry themselves and pick any bucket. Neither is wrong for a demo; 2 suits
   real use through the site. **Check on staging** (in the operations notes): from one network, fail sign-in on 30
   different demo emails within a minute through the Vercel site; if a teammate on another network is then
   throttled too, the buckets are shared and the count should be 2.
   **Update, 23 Nov:** staging moved to one Vercel project, so the site and the API share Vercel's edge and there is no
   second proxy. The edge sets `X-Forwarded-For` to the visitor's address and the count is 1 there by default
   (`backend/config/settings.py`), so each visitor has their own bucket. The sign-in counts are kept in the database
   on Vercel, because several copies of the API run at once. The two-network check still stands for the operations
   notes.
3. **Throttle rates.** The defaults are 30 per minute for login and 30 per hour for signup, per address. A hospital's
   computers often share one address (the per-account lockout exists for that reason), so a stricter rate would lock out
   a ward.
4. **Frontend copy for a throttled login, fixed (22 Nov).** `frontend/src/api/auth.ts` mapped every 429 to the lockout
   message, "Wait 15 minutes", though a throttled request waits about a minute, and a throttled sign-up read as "the
   server didn't respond". It now tells the two apart by the reply (DRF's throttle reply starts "Request was
   throttled"): throttled sign-ins and sign-ups say "Too many attempts from this network just now. Wait a minute and
   try again." Tests: `frontend/src/api/auth.test.ts`.
5. **Silenced W021.** See above. The spec's acceptance line "prints no issues" holds with one check silenced on purpose.

## Follow-ups (not done in B13)

- **Staging checks (after merge, recorded in the operations notes):** `check --deploy` on the staging service
  (spec acceptance); `/api/health/` passes Render's check with the HTTPS redirect on; `/admin/` answers 404 on
  staging; HSTS arrives through Vercel's `/api` proxy and on the Vercel domain; `DJANGO_TRUSTED_PROXY_COUNT` gives
  each user its own sign-in bucket (decision 2).
- **Postgres run of the load test: done (22 Nov).** `docs/testing/search-load-test.md` records PostgreSQL 16: p95 about
  26 ms at concurrency 1 and 108 to 139 ms at concurrency 5, with a same-machine SQLite comparison.
- **Follow-up issues: filed (22 Nov), fixed (23 Nov).** F5 was [#122](https://github.com/harishassan-code/hospital-care/issues/122)
  (names now only for signed-in staff) and F7 [#123](https://github.com/harishassan-code/hospital-care/issues/123)
  (stock now per hospital); the Product Owner can still ask for another option. The frontend copy for a throttled
  sign-in (decision 4) was fixed on 22 Nov.
- **Decisions for the Product Owner:** decision 1 (the Vercel `includeSubDomains` header, which the spec's non-goals
  do not allow for hosts other than the API); decision 3 (the throttle rates); and when to raise HSTS to one year
  (spec Q6 says after a week of HTTPS-only staging).
- **Not changed, by design:** the GET-time sweeps (F9) and the demo logins, which stay public for the demo (spec
  non-goals).
