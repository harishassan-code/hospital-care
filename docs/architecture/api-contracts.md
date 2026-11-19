# API contracts: Sprint 2

Agreed before building. The frontend tests mock exactly these shapes (`frontend/src/test/mockApi.ts`), and the
backend tests check them. The Sprint 1 endpoints are in [api.md](api.md). Same conventions apply: JSON, session
cookie + `X-CSRFToken` on writes, camelCase field names.

Common errors on every endpoint below: **403** when signed out or the role lacks access, **404** for an
unknown id, **400** `{field: ["message"]}` for invalid input.

## Access (stories 1.2)

`ACCESS` in `backend/apps/accounts/permissions.py` and `frontend/src/features/staff/roles.ts` must stay
identical. Reads need *view*, writes need *edit*.

| Role | overview | emergencies | beds | blood | pharmacy | hospitals | specialists | users | equipment | operatingRooms | orBookings | transfers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| admin | view | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit |
| doctor | view | edit | view | view | view | view | view | – | view | view | edit | edit |
| nurse | view | edit | edit | – | view | view | edit | – | edit | edit | edit | edit |
| bloodBank | view | view | – | edit | – | view | view | – | – | – | – | edit |
| pharmacist | view | view | – | – | edit | view | view | – | – | – | – | – |
| patient | – | – | – | – | – | – | – | – | – | – | – | – |

`emergencies` was added in Sprint 7 with #30 (see [api.md](api.md#emergency-cases-30-32)). `transfers` was added with
B01 (#47): it lets a role use the transfer endpoints at all. Who may ask, approve, ship or receive is narrowed per move
(see [transfers](api.md#transfers-47-48-49)). `specialists` was added with B16 (#61, #62): every staff role reads the
whole network, a nurse edits her own hospital only, and an admin edits any hospital (see
[specialists](#specialists-61-62)).

`orBookings` (story #29) is the module for booking and cancelling operating room slots. It has no nav item of its own: the day schedule is part of operating rooms.

**Own hospital only:** a user who isn't an admin may change a resource only if it belongs to their own
hospital (`resource.hospital == user.hospital`); otherwise **403**. Admins manage the whole network.
The bed board (`GET /beds/`) and blood list (`GET /blood/units/`) only return the user's hospital when they
have one. Pharmacy has no hospital yet.

`User` (from `/auth/me/`, `/auth/login/`) gains `hospital: {id, name} | null`.

## Users (story 1.2 Role management)

| Method | Path | Access | Body | Success |
|---|---|---|---|---|
| GET | `/users/` | users: view | – | 200 `UserSummary[]`, sorted by email |
| PATCH | `/users/<id>/` | users: edit | `{role}` | 200 `UserSummary` |

```ts
UserSummary = {
  id: number, email: string, fullName: string,
  role: 'admin' | 'doctor' | 'nurse' | 'bloodBank' | 'pharmacist' | 'patient',
  hospital: { id: number, name: string } | null,
  isActive: boolean,
  roleLocked: boolean   // true for your own account and for superusers: PATCH answers 400
}
```

- 400 `{role: ["…is not a valid choice."]}` for an unknown role.
- 400 `{role: ["You can't change your own role."]}`: stops an admin locking themselves out.
- 400 `{role: ["This account is a superuser. Change it in Django admin."]}`: a superuser always acts as admin.
- Every change writes an audit entry `user.role_changed` with `{role}` before and after.
- The new role applies on the user's next request. The SPA reads `/auth/me/` on every page load.

## Hospitals (story 1.3 Hospital registration and capability profile)

| Method | Path | Access | Body | Success |
|---|---|---|---|---|
| GET | `/hospitals/` | hospitals: view | – | 200 `Hospital[]`, active and deactivated, sorted by name |
| POST | `/hospitals/` | hospitals: edit | `HospitalInput` | 201 `Hospital` |
| GET | `/hospitals/<id>/` | hospitals: view | – | 200 `HospitalDetail` |
| PATCH | `/hospitals/<id>/` | hospitals: edit | any part of `HospitalInput` | 200 `Hospital` |
| GET | `/hospitals/capabilities/` | hospitals: view | – | 200 `Capability[]`, the managed list |

```ts
HospitalType = 'hospital' | 'bloodBank'
HospitalInput = {
  name: string,              // required, ≤ 150, unique (case-insensitive)
  type: HospitalType,        // required
  address: string,           // required, ≤ 300
  latitude: number,          // required, -90 … 90, up to 6 decimals
  longitude: number,         // required, -180 … 180, up to 6 decimals
  phone?: string,            // optional, digits, spaces, + or -, 7–20 characters
  isActive?: boolean,        // default true; PATCH {isActive: false} deactivates
  capabilities?: string[]    // Capability codes; responses list them in the managed list's order (by name)
}
Hospital = HospitalInput & { id: number, phone: string, isActive: boolean, capabilities: string[] }
Capability = { code: string, name: string }
HospitalDetail = Hospital & { departments: Department[], wards: WardItem[], locations: LocationItem[] }
```

There is no DELETE: hospitals are deactivated, never removed, so history and audit entries keep their target.
Deactivated hospitals stay in the list (marked) and must be excluded from matching (Sprint 6).
Search and the type filter run in the browser on the full list.

Audit actions: `hospital.created` (after), `hospital.updated` (changed fields before and after).

## Hospital structure (story 1.3 Hospital structure)

| Method | Path | Access | Body | Success |
|---|---|---|---|---|
| POST | `/hospitals/<id>/departments/` | hospitals: edit | `{name}` | 201 `Department` |
| POST | `/hospitals/<id>/wards/` | hospitals: edit | `{name, kind, departmentId?}` | 201 `WardItem` |
| POST | `/hospitals/<id>/locations/` | hospitals: edit | `{name}` | 201 `LocationItem` |
| DELETE | `/hospitals/<id>/<departments\|wards\|locations>/<item id>/` | hospitals: edit | – | 204 |

```ts
Department = { id: number, name: string }
WardItem = { id: number, code: string, name: string, kind: string, departmentId: number | null, bedCount: number }
LocationItem = { id: number, name: string }
```

- Each item belongs to exactly one hospital. Names are unique within a hospital, so a duplicate returns 400 `{name: […]}`.
- `departmentId` must be a department of the same hospital (400 otherwise).
- DELETE answers **409** `{detail}` when something still uses the item: a ward with beds, or a location a
  resource is stored in. Deleting a department leaves its wards without a department.
- `code` is generated (the bed board's ward id) and never changes.
- Audit actions: `department.created`/`deleted`, `ward.created`/`deleted`, `location.created`/`deleted`.

## Bed types (story 2.1 Bed registry, #23)

Each `Bed` in `GET /beds/` gains `type`: `'icu' | 'emergency' | 'general' | 'isolation' | 'nicu'`.
Occupancy per type and the alert threshold (`occupancyAlertPercent` in `frontend/src/config/hospital.ts`) are
worked out in the browser from the board. There's no new endpoint.

## Resource status (task 2.0)

There's no new endpoint. `POST /beds/<id>/actions/` now runs through the shared state machine
(`apps/resources`). It records who, when, from, to and why in `StatusChange`, writes the audit entry
`bed.status_changed`, and answers 403 for a bed in another hospital (non-admins).

## Specialists (#61, #62)

Module `specialists` (B16). Every staff role reads the whole network, so a coordinator can find a specialist at another
hospital. Admins write for any hospital, a nurse writes for her own hospital only, and doctors, blood bank and pharmacy
staff only read. Patients get 403. The rules are in `apps/specialists/services.py`.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/specialists/?hospital=&specialty=&availableNow=true` | – | 200 `SpecialistSummary[]` |
| POST | `/specialists/` | `SpecialistInput` | 201 `SpecialistDetail` |
| GET | `/specialists/<id>/` | – | 200 `SpecialistDetail` |
| PATCH | `/specialists/<id>/` | `{name?, specialty?, isActive?}` | 200 `SpecialistDetail` |
| POST | `/specialists/<id>/on-call/` | `{startsAt, endsAt}` | 201 `OnCallWindow` |
| DELETE | `/specialists/<id>/on-call/<window id>/` | – | 204 |

```ts
SpecialistInput = { name: string, specialty: string, hospitalId: number }  // all required
SpecialistSummary = { id: number, name: string, specialty: string, isActive: boolean,
  hospital: { id: number, name: string }, onCallNow: boolean, onCallUntil: string | null }
SpecialistDetail = SpecialistSummary & { onCall: OnCallWindow[] }           // windows not yet ended, by start
OnCallWindow = { id: number, startsAt: string, endsAt: string }             // ISO with offset: "2030-01-15T20:00:00+05:00"
```

- **Filters.** `hospital` (an id), `specialty` (free text, matched case-insensitively) and `availableNow=true` combine.
  `availableNow` uses the server's clock. Rows come by hospital name, then specialty, then name. A non-numeric `hospital`
  or a non-boolean `availableNow` is 400.
- **Available now.** A specialist is on call when they are active and one window has `startsAt <= now < endsAt`: start
  inclusive, end exclusive. `onCallUntil` is the end of that window, and `null` when the specialist isn't on call. That
  includes a deactivated specialist who is inside a window.
- **Windows.** Times are stored in UTC and shown in Asia/Karachi. An overnight window is one entry (Monday 20:00 to Tuesday
  08:00). Two windows of one specialist may not overlap, but one that starts as another ends is fine. A window must end after
  it starts and must not have ended when it is added. Removing a window that has started is **409** `{detail}`: it stays as
  history. A window that belongs to another specialist is 404.
- **Profiles.** Never deleted. `isActive: false` keeps the profile, marked, and takes it off call at once. `hospitalId` is
  set on create and can't change. A name is unique per hospital, in any case.
- **Refusals.** Every refusal names its field: `{"endsAt": [...]}` (not after the start, or already ended),
  `{"startsAt": ["Overlaps an on-call window from 16 Jan 08:00 to 16 Jan 20:00."]}`, `{"name": [...]}` (taken at the hospital),
  `{"hospitalId": [...]}` (unknown or deactivated hospital). A role that may not edit, or a non-admin writing for another
  hospital, gets **403** `{detail}`. An unknown specialist is 404.
- **Public page.** `/public/status/` is unchanged. It never lists staff specialists.
- **Audit:** `specialist.created` (after: name, specialty, hospital), `specialist.updated` (only the fields that changed,
  before and after), `on_call.created` (after: startsAt, endsAt) and `on_call.deleted` (before: startsAt, endsAt). The
  target of an `on_call` entry is the window.
- **Admin:** read-only, the same as transfers, so every change goes through the app and is audit-logged.

## Audit (story 8.1)

There's no endpoint in Sprint 2. Entries are append-only (the model refuses update and delete), so the API can
neither edit nor delete them. Admins read them in Django admin (`/admin/audit/auditlog/`, read-only). Search and
export come with issue #56 in Sprint 8.
