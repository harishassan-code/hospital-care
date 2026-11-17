# Construction Plan: Emergency blood request

**Spec:** [docs/aidlc/inception/2026-11-17-emergency-blood-request.md](../inception/2026-11-17-emergency-blood-request.md)
**Date:** 2026-11-17

## Design

- **No new model.** A blood request is an `EmergencyRequest` with one `RequestItem` of type `blood`. Urgency is
  `severity`. `create_case` and its serializer already cover the acceptance criteria: quantity 1 to 20 (`MAX_QUANTITY`),
  `group` and `component` as `BloodGroup` and `Component` choices, `severity` as a choice. The new tests pin each one
  for the blood path. No serializer change was needed.
- **Quick form:** `BloodRequestForm` on the Emergencies page, opened by a "Request blood" button beside "New case" for
  roles with emergencies edit. One step, four fields: group, component, quantity (whole number, 1 to 20) and urgency
  (the four severities). It posts `POST /emergencies/` with one blood item and `patientRef: ""`, then navigates to
  `/staff/emergencies/<reference>`. A 400 is mapped to its field the same way the full form does it.
- **Feed endpoint:** `GET /emergencies/feed/?type=blood|bed` in `EmergencyFeedView`. Route is placed before
  `<str:reference>/` in `case_urls.py`. The view runs `escalate_overdue()` first, like the list and detail. Its queryset:
  statuses `open`, `matching`, `partiallyFulfilled`, `escalated`, across every hospital; `Exists` on a need of the
  requested type; `select_related("hospital")`; `Prefetch("items")` filtered to that type; `by_priority()`; sliced to 100.
  Serialized by `FeedEntrySerializer`, which has no `patientRef`, `createdBy`, `history` or `notes`.
- **Permission:** `module_permission("emergencies")`, so view for every role that can see emergencies. Patients and
  anonymous users get 403.
- **Feed page:** `EmergencyFeedPage` at `/staff/emergencies/feed`, linked from the Emergencies page. A type toggle
  (Blood, Beds) with radio buttons. The list is a child keyed by the type, so each toggle loads again. Each entry shows
  the hospital, the reference (a link only when the hospital is the user's own, as `user.hospital.id`), severity as a
  `StatusBadge` with its label, the status (`CaseStatusLabel`), the age ("12 minutes ago"), and the needs with
  `describeNeed`. An empty state for each type.
- **Age:** `formatAgo(iso, now)` in `lib/time.ts`, using `Intl.RelativeTimeFormat`. No new dependency.
- **Mocks:** `mockApi` passes the request's query string to handlers. `GET /emergencies/feed/` is registered before
  `GET /emergencies/:reference/` (the matcher would take "feed" for a reference otherwise). It filters the sample
  cases the same way the server does. The feed sample lives in `test/fixtures/emergencies.ts`.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend: the blood validation tests, the feed endpoint and serializer, the route, the docs | `backend/apps/emergencies/{views,serializers,case_urls}.py`, `backend/apps/emergencies/tests/test_blood_request.py`, `backend/apps/emergencies/tests/test_feed.py`, `docs/architecture/api.md` | pytest: blood quantity 0, −1, non-integer, unsupported component, unsupported group, missing component are 400 with a field error; valid blood request is 201 with reference, `open` and a history entry; feed includes other hospitals' active cases, excludes fulfilled, closed and cancelled, excludes cases without a need of the type; ordering by severity then age; `type=bed`; bad type is 400; no `patientRef`; roles and 403s; the feed runs the escalation sweep; query count does not grow with the number of cases |
| 2 | Frontend: API types and calls, `formatAgo`, the quick form, the feed page, the Emergencies page links, the route, mocks and fixtures | `frontend/src/api/emergencies.ts`, `frontend/src/features/emergencies/{emergencies.ts,BloodRequestForm.tsx,Emergencies.module.css}`, `frontend/src/lib/time.ts` (+ test), `frontend/src/pages/staff/EmergenciesPage.tsx` (+ test), `frontend/src/pages/staff/EmergencyFeedPage.tsx` (+ test), `frontend/src/App.tsx`, `frontend/src/test/mockApi.ts`, `frontend/src/test/fixtures/emergencies.ts` | vitest: quick form validates and posts one blood item, then navigates to the case; a server 400 shows on the field; the feed lists entries in server order with severity, status and needs; own-hospital entries link and others do not; the type toggle refetches; empty state; view-only roles see the feed and not the quick form |

## Sequencing

Unit 1 before unit 2: the frontend types follow the API response that unit 1 makes real.

## Ponytail notes

- **Feed limit:** a slice of 100 with no paging. Ceiling: a network with more than 100 active requests of one type will
  not show the rest. Add paging when that happens.
- **Escalation sweep:** the feed reuses the request-time sweep, the same ceiling as the list (#35).

## Test plan

- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && pytest`
  on SQLite and on Postgres. No migration is expected.
- `cd frontend && npm run lint && npm test && npm run build`.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified:** Postgres, full suite: 415 passed. SQLite, full suite: 414 passed and one failure that is not this story's
  (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, a known SQLite issue). Ruff check and format,
  and `makemigrations --check`, clean (no migration). Frontend: lint clean, 313 tests pass (35 files), build succeeds.
- **The validation already covered the acceptance criteria.** Quantity 0, −1, a non-integer, 21, an unsupported
  component or group, and a missing group, component or quantity all return 400 with a field error, and nothing is
  saved. `test_blood_request.py` pins each one. The serializer needed no change.
- **Feed entries carry `hospital` as `{id, name}`,** the same shape as a case's. The spec said the name. The id lets the
  page tell the user's own hospital apart without comparing names, which two hospitals could share.
- **`reference` is the entry's key,** not `id`, as the spec named it. The case shape keeps `id`. The two shapes differ on
  purpose: the feed is not a case.
- **`?type=` with an empty value falls back to blood** (DRF's default for an empty choice). Only a value that is not a
  choice is a 400. Tests cover `equipment` and `BLOOD`.
- **The feed cap is tested with 101 cases.** The 100 kept are the most urgent; the newest low-severity case is the one
  left out, because within a severity the oldest case comes first.
- **Query count is fixed at three** whatever the number of cases: the sweep's check, the cases with their hospitals,
  and their needs. The test compares a 2-case feed with an 8-case feed.
- **`TextField` takes `type="number"` and `min`/`max`** for the quick form's units input, as the spec asked for a number
  input. No other behaviour of the shared field changed.
- **Mock API:** `mockApi` now passes the request's query string to handlers. The feed route is registered before the
  `:reference` route. The mock sorts and filters the feed the way the server does, so its tests are about the page, not
  the mock.
