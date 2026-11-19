# Inception Spec: Specialist profiles and on-call availability

**Date:** 2026-11-18
**Author:** Claude, drafted for review
**Bolt:** [B16](../bolts/B16-specialists.md)
**Related backlog items:** #61 Specialist doctor profiles, #62 Specialist on-call availability (Epic E2, WBS 2.4;
stretch). Builds on the public doctor schedule (`DoctorShift`, `/api/public/status/`) and the access table
(`backend/apps/accounts/permissions.py`, `frontend/src/features/staff/roles.ts`).

## Problem

Today the public home page lists the day's doctors with department and hours, but it does not say which hospital
each doctor works at, and it cannot say who is on call on a given night. Staff have no list of the specialists each
hospital has. When a case needs a cardiologist, the coordinator has no single place to see who is available.

This is for the emergency coordinator and for staff at each hospital. There is no coordinator role: coordinators are
staff in the roles below, so the list is open to every staff role. Patients need nothing here. The public page already
shows doctors without sign-in, and that stays as it is.

## User stories

- As a coordinator, I want to see each hospital's specialists and their specialties, so that I know who a case can ask
  for. (#61)
- As a nurse at a hospital, I want to record a specialist's on-call times, so that the network knows who is on call.
  (#62)
- As a coordinator, I want to filter to the specialists on call now, so that I can see who is reachable at this hour.
  (#62)

## Acceptance criteria

### #61 Specialist doctor profiles

- [x] Profile has specialty and hospital. Each profile has a name, a specialty (free text, e.g. "Cardiology") and one
      hospital. The hospital is required.
- [x] The profile shows its hospital, and the staff list can be filtered by hospital and by specialty.
- [x] A profile is deactivated, never deleted. A deactivated profile stays in the list, marked, and is never on call.
- [x] Creating or editing a profile needs edit rights on `specialists` (see Design). A non-admin gets 403 for another
      hospital's profile.

### #62 On-call schedule per specialist; "Available now" filter

- [x] Each specialist has on-call windows, each with a start and an end (date and time). Windows can be added and
      removed.
- [x] "Available now" filter: the list can show only the specialists on call at the moment of the request. Each row
      says until when ("On call until 08:00") or "Not on call".
- [x] A window must end after it starts. Two windows for the same specialist may not overlap (400).
- [x] A window can be added only if it has not ended yet. Only a window that has not started can be removed (409
      otherwise). Past windows stay as history.
- [x] The public landing page and `/api/public/status/` do not change.

### Common

- [x] Each change (profile created or updated, window added or removed) writes an audit record (see Design).
- [x] Every endpoint has a permission class and a test. The access table is identical in the backend, in `roles.ts`
      and in `docs/architecture/api-contracts.md`.
- [x] Seed data gives every demo hospital specialists with on-call windows. `seed_demo --reset` removes them.

## Non-goals

- Booking a specialist, or assigning one to a case or a transfer (the bolt's "Booking specialists").
- Changing the public doctor schedule or its endpoint. The public page keeps `DoctorShift`.
- Recurring rota patterns such as a weekly template. Each window is its own row, entered by hand or made by the seed.
- Leave, sickness, workload or "in theatre" status. "Available" means "on call now" and nothing more.
- Phone or pager numbers on profiles. These are personal contact details and need a separate decision.
- Moving a specialist to another hospital. Create a new profile and deactivate the old one.
- Notifications when an on-call window starts (B06).
- Doctors editing their own rota, and time zones other than Asia/Karachi.

## Design

### Models: what exists today

`DoctorShift` (`hospitals` app, migration 0001, not changed since) is the only doctor model. The public page reads it
through `DoctorSerializer`, which exposes `id`, `name`, `department`, `start` and `end`. `seed_demo` creates 14 of them.

| Field | Today | Enough for B16? |
|---|---|---|
| `name`, `is_active` | CharField(150), bool | Yes |
| `department` | CharField(100), free text, no FK | Yes, as the specialty. The public filter already uses it. |
| `start`, `end` | TimeField only. `end` earlier than `start` means past midnight. | No. It is a daily pattern with no date, so it cannot hold a one-off on-call. |
| hospital | **missing** | No. A shift has no hospital. |
| on-call window | **missing** | No. |

Proposed (answers the bolt's open question): **a separate staff-only model**, in a new app `apps/specialists/`. That
follows the one-app-per-resource pattern of `equipment` and `operating_rooms`. The architecture README row that lists
`Specialist` under `resources` is updated to match.

- `Specialist`: `hospital` (FK to `hospitals.Hospital`, PROTECT, required), `name` (CharField 150), `specialty`
  (CharField 100), `is_active` (default true). Unique per hospital on `Lower(name)`.
- `OnCallWindow`: `specialist` (FK, PROTECT), `starts_at`, `ends_at` (DateTimeField, stored in UTC). A database check
  requires `ends_at > starts_at`. Overlap is an application rule, checked in `services.py` under a row lock on the
  specialist. A plain database constraint cannot express it on SQLite.

Why not reuse `DoctorShift`: it has no hospital, and a daily time pattern cannot express "on call Thursday 20:00 to
Friday 08:00". Adding both fields would also change the shape of the public data. The cost of a separate model is that
the same doctors appear twice (open question 1).

### Endpoints

Base `/api/specialists/`. Module `specialists`. Errors follow `api-contracts.md`.

| Method | Path | Access | Body | Success |
|---|---|---|---|---|
| GET | `/specialists/?hospital=&specialty=&availableNow=true` | specialists: view | – | 200 `SpecialistSummary[]` |
| POST | `/specialists/` | specialists: edit (own hospital) | `SpecialistInput` | 201 `SpecialistDetail` |
| GET | `/specialists/<id>/` | specialists: view | – | 200 `SpecialistDetail` |
| PATCH | `/specialists/<id>/` | specialists: edit (own hospital) | `{name?, specialty?, isActive?}` | 200 `SpecialistDetail` |
| POST | `/specialists/<id>/on-call/` | specialists: edit (own hospital) | `{startsAt, endsAt}` | 201 `OnCallWindow` |
| DELETE | `/specialists/<id>/on-call/<window id>/` | specialists: edit (own hospital) | – | 204 |

```ts
SpecialistInput = { name: string, specialty: string, hospitalId: number }  // all required
SpecialistSummary = { id, name, specialty, isActive, hospital: {id, name},
  onCallNow: boolean, onCallUntil: string | null }   // end of the window covering now, ISO
SpecialistDetail = SpecialistSummary & { onCall: OnCallWindow[] }          // windows not yet ended, by start
OnCallWindow = { id: number, startsAt: string, endsAt: string }            // ISO with offset, e.g. +05:00
```

`hospitalId` is set on create and cannot change (non-goal). Validation errors are 400 with the field name:
`endsAt` must be after `startsAt`, the window must not overlap the specialist's other windows, and `endsAt` must be in
the future. A non-admin who writes for another hospital gets 403. Unknown ids get 404. Deleting a window that has
started gets 409.

The public endpoint `/api/public/status/` is unchanged. A test confirms that staff profiles never appear in it.

### Permissions (both places)

Add a `specialists` module to `ACCESS` in `backend/apps/accounts/permissions.py`, to `ACCESS` in
`frontend/src/features/staff/roles.ts`, and to the access table in `api-contracts.md`:

| Role | specialists |
|---|---|
| admin | edit (any hospital) |
| doctor | view |
| nurse | edit (own hospital) |
| bloodBank | view |
| pharmacist | view |
| patient | – |

Reads are network-wide for every staff role. This is the one endpoint family that does not use `own_hospital()`,
because a coordinator must find a specialist at another hospital. Writes go through `may_change(user, specialist)`:
admin can write anywhere, and other roles only where the specialist's hospital is their own.

Frontend nav: add `{ id: 'specialists', label: 'Specialists', path: '/staff/specialists' }` to `MODULES`, after
Hospitals. Nothing comes out of `planned.ts`, because B16 was never listed there.

### Frontend

- `frontend/src/api/specialists.ts` holds the API calls. Hospital options come from the existing `/hospitals/` list.
- `pages/staff/SpecialistsPage.tsx` at `/staff/specialists`: a list with hospital and specialty filters, an **Available
  now** toggle (sends `availableNow=true`), and the on-call text for each row. An "Add specialist" button shows for edit
  roles only.
- `pages/staff/SpecialistFormPage.tsx` at `/staff/specialists/new`, and `pages/staff/SpecialistDetailPage.tsx` at
  `/staff/specialists/:id`. The detail page shows the profile, the upcoming windows, an add-window form (date and time)
  and remove for a window not yet started. This follows the pattern of the hospital pages.
- Times are shown and entered in Asia/Karachi, and the form sends the `+05:00` offset. Karachi has no daylight saving
  time, so the fixed offset is exact. Revisit this if that changes.
- The list loads on each visit, and the toggle reloads it. There is no polling in B16.
- New endpoints are mocked in `frontend/src/test/mockApi.ts`.

### "Available now" semantics

- **Now** is the server clock (`timezone.now()`), read once per request. The browser's clock is not used.
- A specialist is available now when the specialist is active and some window has `starts_at <= now < ends_at`. Start is
  inclusive and end is exclusive, the same rule as `isInNow` on the public page.
- **Overnight:** a window is two absolute times. Monday 20:00 to Tuesday 08:00 is one window that ends the next morning.
  The "end earlier than start" rule of `DoctorShift` does not apply.
- **Time zone:** stored as UTC. Entered and shown in `settings.TIME_ZONE` (Asia/Karachi). Only instants are compared, so
  a viewer's zone does not change the answer.
- **Overlap:** the rule means at most one window covers any instant, so `onCallUntil` is unambiguous.
- "Available" means on call. The system does not know about leave, workload or procedures.

Known gap, outside B16: the public page's "In now" uses the browser clock (`lib/time.ts`), so a viewer outside Karachi
sees the wrong answer. The staff page avoids this by using server time in Karachi.

### Audit

Each write calls `apps.audit.services.record` inside the same transaction:

- `specialist.created` (after: name, specialty, hospital)
- `specialist.updated` (before and after: the changed fields only)
- `on_call.created` (after: startsAt, endsAt; the target is the window)
- `on_call.deleted` (before: startsAt, endsAt)

### Seed data

`seed_demo` adds specialists only when there are none, like its other sections:

- The 14 names in `DOCTORS` become specialists, with `specialty` set to their department. Cardiology goes to Seaview,
  Paediatrics to Northside, and the rest to CityCare General. Orthopaedics and Gynaecology have no department at any demo
  site, which is fine for free text.
- Each specialist gets one on-call window per day for the next 7 days (Karachi time), built from the same start and end
  times. An overnight shift becomes one window that ends the next morning.
- `--reset` deletes `OnCallWindow` before `Specialist` (PROTECT), like `OrBooking` before `OperatingRoom`.

### Tests

- Backend, `apps/specialists/tests/`:
  - `available_now` at the boundaries (start in, end out), for an overnight window, for an inactive specialist, and for
    windows in the past or future. Karachi input is stored as the matching UTC instant.
  - Window rules: end after start, overlap refused, back-to-back allowed, end in the past refused, and a started window
    cannot be deleted.
  - API: the `availableNow` filter, and audit rows for each write.
- `accounts/tests/test_permissions.py`: add the `specialists` rows to `ENDPOINTS`, so each role gets exactly its access.
  A nurse can write only for her own hospital (403 otherwise) and can read every hospital.
- Public: `/api/public/status/` does not include specialists.
- Seed: creates the data once, adds nothing on a re-run, and `--reset` works.
- CI: `makemigrations --check`.
- Frontend: `roles.test.ts` (the `TABLE` rows and the exact `MODULES` list, which gains `specialists`);
  `SpecialistsPage.test.tsx` (filters, the toggle, "Not on call", no add button for a doctor); and
  `SpecialistDetailPage.test.tsx` (adding a window, and the overlap error shown). In `features.qa.test.tsx`, check for
  "Specialists" with `arrayContaining` only.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Reuse the public doctor model, or a separate staff-only one?** (The bolt's question.) *Proposed:* a separate
   `Specialist` and `OnCallWindow` (see Design). `DoctorShift` and the public page stay as they are. The alternative is to
   add a hospital field to `DoctorShift` and keep a daily pattern. That is smaller, but it cannot express dated on-call
   and it changes the public data. If the team wants one record per doctor later, link `DoctorShift` to `Specialist` in
   a follow-up.
2. **Who edits on-call times?** *Proposed:* admin (any hospital) and nurse (own hospital). Doctors and other roles can
   only view. The alternative is admin only.
3. **Are reads network-wide?** *Proposed:* yes, for every staff role, so a coordinator can see specialists at other
   hospitals.
4. **Specialty as free text, or a managed list like `Capability`?** *Proposed:* free text. It matches `DoctorShift.department`
   and the seed, and the filter lists the values in use. The alternative is an admin-managed list, which needs its own
   admin page.
5. **Should the public page move to the on-call data later?** *Proposed:* not in B16. Once the team agrees on one roster,
   a follow-up can point the public page at it.

## Approval

- [x] Approved by: Krrishna on 2026-11-18 (proposed answers accepted as written)
