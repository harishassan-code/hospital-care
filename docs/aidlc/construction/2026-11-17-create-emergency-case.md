# Construction Plan: Create an emergency case

**Spec:** [docs/aidlc/inception/2026-11-17-create-emergency-case.md](../inception/2026-11-17-create-emergency-case.md)
**Date:** 2026-11-17

## Design

Follows the ERD's planned `EmergencyRequest` and `RequestItem` ([erd.md](../../architecture/erd.md)) and the
"New emergency request" wireframe ([wireframes.md](../../product/wireframes.md)).

- `EmergencyRequest`: `reference` (unique, `EC-<year>-<seq>`), `hospital`, `created_by`, `severity`
  (critical/urgent/routine), `status` (all seven ERD statuses as choices, default `open`), `patient_ref`
  (optional, ≤ 30 chars), `created_at`.
- `RequestItem`: `request`, `resource_type` (blood/bed), `blood_group`, `component`, `bed_type`, `quantity`
  (> 0, DB check), `fulfilled` (0 for now; matching and allocation fill it later).
- **The reference is safe under concurrency:** the next sequence number comes from the year's highest
  reference, the unique constraint catches a race, and the create retries. (Donor codes don't do this.)
- **One deviation from the spec:** the spec says status uses the shared `StateMachine`. This story has no
  transitions (only `open`), and an empty machine would be dead code, so the machine is added in #34 along
  with its transitions. The status field already has all seven ERD choices, so #34 needs no new choices.
- Access: new `emergencies` module. Admin, doctor and nurse can edit; blood bank and pharmacist can view.
  Users at a hospital see that hospital's cases; staff with no hospital see all of them (the same rule as
  blood, via a shared `own_hospital` helper that moves to `accounts/permissions.py`).

API (`/api/emergencies/`, camelCase like the rest):

```
GET  /emergencies/              → EmergencyCase[] (newest first)           emergencies: view
POST /emergencies/              {severity, patientRef?, items[]} → 201      emergencies: edit
GET  /emergencies/<reference>/  → EmergencyCase                             emergencies: view
EmergencyCase = { id: "EC-2026-0001", severity, status, patientRef, hospital: {id, name} | null,
                  createdBy: string, createdAt, items: RequestItem[] }
RequestItem   = { type: "blood", group, component, quantity } | { type: "bed", bedType, quantity }
```

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend: models + migration, reference generation, serializers, `create_case` service (atomic, audit-logged), list/create/detail views, `emergencies` access rule, admin, API docs | `backend/apps/emergencies/{models,serializers,services,views,urls,admin}.py`, migration `0002`, `backend/apps/accounts/permissions.py`, `backend/apps/blood/views.py` (uses the moved helper), `backend/config/urls.py`, `docs/architecture/api.md` | pytest: create → `open` + reference + audit entry; references are sequential per year; no patient data needed; item validation (1–10 items, blood/bed fields, quantity limits); role access matrix; own-hospital scoping on list and detail |
| 2 | Frontend: `api/emergencies.ts`, `emergencies` module in `roles.ts`, Emergencies page (case list + 3-step "New case" form), validation; leaves `PLANNED` | `frontend/src/api/emergencies.ts`, `frontend/src/features/staff/{roles,planned}.ts`, `frontend/src/features/emergencies/*`, `frontend/src/pages/staff/EmergenciesPage.tsx`, `frontend/src/App.tsx`, `frontend/src/test/{mockApi.ts,fixtures/emergencies.ts}` | vitest: list renders; editors see "New case", viewers don't; the 3 steps with Back/Next; step validation (at least one item, quantity limits); submit adds the case with its reference; a server 400 or 403 is shown |

## Sequencing

Unit 1 before unit 2: the frontend mocks follow the API contract above, which unit 1 makes real.

## Test plan

- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && pytest`
- `cd frontend && npm run lint && npx tsc -b && npm test && npm run build`
- Manual: `seed_demo`, sign in as `doctor@demo.citycare.pk`, create a case with 4 × O- red cells and an ICU
  bed, and see it listed as `open` with an `EC-…` reference. As `bloodbank@…` the list shows but there's
  no "New case".

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Bug found and fixed in a shared helper:** `own_hospital()` handed back the queryset it was given
  unchanged for staff with no hospital. A module-level queryset passed in got evaluated and cached, so admins
  would have seen a frozen case list until the server restarted. It now always returns a fresh queryset
  (`backend/apps/accounts/permissions.py`), with a regression test. Blood was never affected (its views
  build a fresh queryset per request), but now can't be.
- DRF 3.18 reports errors on one item of a list as `{"items": {"0": {...}}}`, keyed by position. The form
  maps them back to the right row (documented in `api.md`).
- Accessibility: the "New case" button disappears when the form opens, so focus moves to the step heading
  on open and on every step, and back to "New case" when the form closes.
- QA case **TC-23** (coordinator signs in to emergency entry) was a `todo`; it now runs as ADAPTED, with a
  doctor standing in for the coordinator role. `mockStaffApi` gained a `POST /auth/login/` route for it.
- Verified against a fresh SQLite database with real migrations and `seed_demo`. The demo doctor opens
  `EC-2026-0001` at CityCare General; blood bank can list but gets 403 on create; a patient gets 403.
