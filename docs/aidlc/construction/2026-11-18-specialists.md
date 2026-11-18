# Construction Plan: Specialist profiles and on-call availability

**Spec:** [docs/aidlc/inception/2026-11-18-specialists.md](../inception/2026-11-18-specialists.md)
**Date:** 2026-11-18

B16 covers #61 (profiles) and #62 (on-call windows and the "Available now" filter). Both share one model and one
module, so they are built on one branch in the order below. The public doctor schedule (`DoctorShift`,
`/api/public/status/`) is not touched.

## Design

### Models (`backend/apps/specialists/models.py`)

- `Specialist`: `hospital` (FK `hospitals.Hospital`, PROTECT, `related_name="specialists"`), `name` (CharField 150),
  `specialty` (CharField 100, free text), `is_active` (default true). Unique per hospital on `Lower("name")`.
  Ordered by name. Never deleted: deactivated instead.
- `OnCallWindow`: `specialist` (FK, PROTECT, `related_name="on_call_windows"`), `starts_at`, `ends_at` (DateTimeField,
  stored in UTC). Check constraint `ends_at > starts_at`. Index on `(specialist, starts_at)`. No overlap constraint:
  that is an application rule (below), because a plain database constraint cannot express it on SQLite.
- `SpecialistQuerySet`:
  - `with_schedule(now)`: `select_related("hospital")` and a prefetch of the windows not yet ended, by start, into
    `upcoming_windows`. The list costs a fixed number of queries.
  - `available_at(now)`: active, and one window with `starts_at <= now < ends_at` (one `.filter()` call, so both
    conditions apply to the same window).

### Services (`backend/apps/specialists/services.py`)

Business rules live here. Views only translate exceptions into status codes. Every write is `@transaction.atomic`
and calls `apps.audit.services.record` in the same transaction.

- `create_specialist(hospital, *, name, specialty, actor)`: `PermissionDenied` (403) unless `may_change` for the
  hospital. `ValidationError` on a duplicate name at the hospital (any case). Audit `specialist.created`.
- `update_specialist(specialist_id, changes, *, actor)`: locks the row. 403 unless `may_change`. Only changed fields
  are written, and only they go in the audit entry (`specialist.updated`, before and after). A duplicate name is
  refused. An unchanged PATCH writes nothing.
- `add_on_call_window(specialist_id, *, starts_at, ends_at, actor)`: locks the specialist (the row lock is what makes
  the overlap check hold). Order of checks: 404, 403, `endsAt` after `startsAt` (400), `endsAt` not in the past (400,
  "has already ended"), overlap (400 on `startsAt`). Overlap is half-open: a window overlaps when
  `a.starts_at < b.ends_at and b.starts_at < a.ends_at`, so back-to-back windows are allowed. Audit `on_call.created`.
- `remove_on_call_window(specialist_id, window_id, *, actor)`: locks the specialist and the window. 404 when the window
  is not on that specialist. 403 unless `may_change`. 409 (`SpecialistConflict`) when `starts_at <= now`. Audit
  `on_call.deleted` is written before the delete, with the start and end in `before`.
- `window_covering(specialist, now)`: the window with `starts_at <= now < ends_at`, from `upcoming_windows`.
- `now` is read once per request with `timezone.now()` and passed down, so one request never sees two clocks.

### API (`backend/apps/specialists/urls.py`, mounted at `/api/specialists/`)

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/specialists/?hospital=&specialty=&availableNow=true` | – | 200 `SpecialistSummary[]` |
| POST | `/specialists/` | `{name, specialty, hospitalId}` | 201 `SpecialistDetail` |
| GET | `/specialists/<id>/` | – | 200 `SpecialistDetail` |
| PATCH | `/specialists/<id>/` | `{name?, specialty?, isActive?}` | 200 `SpecialistDetail` |
| POST | `/specialists/<id>/on-call/` | `{startsAt, endsAt}` | 201 `OnCallWindow` |
| DELETE | `/specialists/<id>/on-call/<window id>/` | – | 204 |

Every view uses `module_permission("specialists")`. The list reads network-wide, because a coordinator must find a
specialist at another hospital. Writes use `may_change` in the services.

Decisions that the spec leaves open, recorded here so review can check them:

- A body reference that does not exist (`hospitalId` unknown or deactivated) is **400** with the field name, following
  the transfers precedent (`supplierId`). Path ids that do not exist are **404**.
- `hospitalId` must be an active hospital when a profile is created. It cannot change afterwards.
- `specialty` filter is case-insensitive exact match (`iexact`). `availableNow` uses the server clock.
- `onCallUntil` is `null` whenever `onCallNow` is false, including for a deactivated specialist with a covering window.

### Access (both places, identical)

`specialists` row added to `ACCESS` in `backend/apps/accounts/permissions.py` and to `ACCESS` in
`frontend/src/features/staff/roles.ts`, and to the access table in `docs/architecture/api-contracts.md`:

| Role | specialists |
|---|---|
| admin | edit (any hospital) |
| doctor | view |
| nurse | edit (own hospital) |
| bloodBank | view |
| pharmacist | view |
| patient | – |

### Frontend

- `src/api/specialists.ts`: types and calls for the six endpoints. Mocked in `src/test/mockApi.ts` against the same shapes.
- `src/features/specialists/schedule.ts`: Asia/Karachi display (`Intl` with `timeZone: "Asia/Karachi"`, so a viewer in any
  zone sees Karachi clock times) and the `+05:00` offset the forms send. Pure functions, tested with fixed instants.
- `pages/staff/SpecialistsPage.tsx` at `/staff/specialists`: table with name, specialty, hospital, status and
  on-call text ("On call until 08:00" with the day when it is not today, or "Not on call"). The **Available now** checkbox
  reloads the list with `availableNow=true`. Hospital and specialty filters run in the browser on the loaded list, as
  the hospitals page does. "Add specialist" shows for edit roles only.
- `pages/staff/SpecialistFormPage.tsx` at `/staff/specialists/new` and `/staff/specialists/:id/edit`: the profile form.
  The hospital select lists only the user's own hospital for a non-admin. The edit route is an addition to the spec's
  routes, following the hospital pages (`hospitals/:id/edit`).
- `pages/staff/SpecialistDetailPage.tsx` at `/staff/specialists/:id`: profile, upcoming windows (remove only for a
  window whose start is still ahead), and the add-window form with start and end date and time (so an overnight window
  is one entry). Overlap and "already ended" errors appear on the field they name.
- Nav: `{ id: "specialists", label: "Specialists", path: "/staff/specialists" }` after Hospitals in `MODULES`.
  `planned.ts` is unchanged, because B16 was never listed there.

### Seed data (`seed_demo`)

- Specialists are created only when there are none. The 14 names in `DOCTORS` each get their department as specialty,
  and a hospital: Cardiology to Seaview, Paediatrics to Northside, all others to CityCare General.
- Each specialist gets one window per day for the next 7 days (Karachi calendar days, from today), built from the
  same start and end times. An overnight shift ends the next morning.
- On a re-run, windows that are missing for the coming 7 days are added (matched by start), so the demo does not go
  stale. Nothing is duplicated. This is a small extension of "adds only when there are none", for windows only.
- `--reset` deletes `OnCallWindow`, then `Specialist`, before `Hospital` (both PROTECT).

### Audit

`specialist.created` (after: name, specialty, hospital), `specialist.updated` (changed fields only, before and after),
`on_call.created` (after: startsAt, endsAt), `on_call.deleted` (before: startsAt, endsAt). The target of the `on_call`
entries is the window.

### Admin

Django admin shows specialists and windows **read-only**. Admin writes would bypass the audit log, so changes are made
in the app. Same reasoning as `apps/transfers/admin.py`.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Construction plan, and the approved inception spec committed with it | `docs/aidlc/construction/2026-11-18-specialists.md`, `docs/aidlc/inception/2026-11-18-specialists.md` | Pre-commit checks |
| 2 | Models, migration, read-only admin, services with the rules and audit; app registered; architecture row | `apps/specialists/{__init__,apps,models,services,admin}.py`, `apps/specialists/migrations/0001_initial.py`, `config/settings.py`, `docs/architecture/README.md` | `apps/specialists/tests/test_services.py`: overlap (including back-to-back), boundaries (start in, end out), overnight, inactive, past and future windows, end-after-start, window in the past refused, started window not removable, audit rows, Karachi input stored as UTC |
| 3 | API: serializers, views, URLs; access rows in backend and `roles.ts`; contracts doc | `apps/specialists/{serializers,views,urls}.py`, `config/urls.py`, `apps/accounts/permissions.py`, `frontend/src/features/staff/roles.ts`, `frontend/src/features/staff/roles.test.ts`, `docs/architecture/api-contracts.md` | `apps/specialists/tests/test_api.py` (every endpoint, each role's 403, hospital scoping on writes, validation, `availableNow` and filters, 404s, 409, audit); `apps/accounts/tests/test_permissions.py` (`ENDPOINTS` rows and own-hospital rule for specialists); `roles.test.ts` (TABLE rows) |
| 4 | Seed: specialists and on-call windows, re-run top-up, reset | `apps/core/management/commands/seed_demo.py`, `docs/architecture/api.md` (demo data) | `apps/core/tests/test_seed_demo.py`: created once, re-run adds nothing, windows cover 7 days, no overlaps, `--reset` |
| 5 | Frontend directory: API client, Karachi helpers, mocks, list page, route, nav | `frontend/src/api/specialists.ts`, `frontend/src/features/specialists/schedule.ts` (+test), `frontend/src/test/fixtures/specialists.ts`, `frontend/src/test/mockApi.ts`, `frontend/src/pages/staff/SpecialistsPage.tsx` (+test), `frontend/src/App.tsx`, `frontend/src/features/staff/roles.ts`, `roles.test.ts` | `api/specialists.test.ts`; `schedule.test.ts`; `SpecialistsPage.test.tsx` (filters, toggle, "Not on call", no add button for doctor, loading, empty, error) |
| 6 | Profile and on-call forms; detail page | `frontend/src/pages/staff/SpecialistFormPage.tsx`, `SpecialistDetailPage.tsx` (+tests), `frontend/src/features/specialists/{SpecialistForm,OnCallForm}.tsx`, `frontend/src/test/mockApi.ts`, `frontend/src/App.tsx` | `SpecialistDetailPage.test.tsx` (adding a window, overlap error shown, remove a future window, 409 on a started one, role gating); `SpecialistFormPage.test.tsx` (create, edit, validation, 403, hospital limited to own for nurses) |
| 7 | QA smoke | `frontend/src/qa/features.qa.test.tsx` | Nav contains Specialists for staff roles (`arrayContaining`), a patient cannot open it, a doctor opens the list and sees no add button |
| 8 | Tick met acceptance criteria in the spec (a separate commit) | `docs/aidlc/inception/2026-11-18-specialists.md` | Pre-commit checks |

The bolt file and the bolt board are not edited by construction. They change when the human sets the bolt's status.

## Sequencing

1. Units 2 to 4 are backend and do not depend on the frontend. Unit 2 comes before unit 3, which needs the services.
2. Unit 3 adds the access row to `roles.ts` before unit 5 adds the nav entry, so a nurse's nav never shows a page the
   role cannot open.
3. Unit 5 needs the API shapes from unit 3 (the mocks copy them).
4. Unit 6 extends the mocks from unit 5.
5. Unit 7 needs the nav entry from unit 5.

## Test plan

- Backend: `apps/specialists/tests/` (services and API), `accounts/tests/test_permissions.py` (access table, which is the
  same rows as `roles.ts`), `apps/core/tests/test_seed_demo.py`. The public endpoint test checks that a new staff profile
  never appears in `/api/public/status/`.
- Frontend: Vitest tests for the API client, the Karachi helpers, the three pages, `roles.test.ts`, and the QA smoke.
  New endpoints are mocked in `src/test/mockApi.ts` so the tests run against the real API shape.
- Checks before every commit (CI runs the same):
  - `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && python -m pytest -q`
  - `cd frontend && npm run lint && npm test && npm run build`
  - `python3 scripts/check_deploy_config.py && python3 scripts/aidlc_board.py --check`
- Not automated: a look at the page on a phone-width screen with the demo seed. The page is a table, as the other staff
  pages are.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md). That approval is the
Construction gate.
