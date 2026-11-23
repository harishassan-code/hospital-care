# API contracts: Sprint 2

Agreed before building. The frontend tests mock exactly these shapes (`frontend/src/test/mockApi.ts`), and the
backend tests check them. The Sprint 1 endpoints are in [api.md](api.md). Same conventions apply: JSON, session
cookie + `X-CSRFToken` on writes, camelCase field names.

Common errors on every endpoint below: **403** when signed out or the role lacks access, **404** for an
unknown id or a record at another hospital (the same reply for both, B13), **400** `{field: ["message"]}` for
invalid input.

## Access (stories 1.2)

`ACCESS` in `backend/apps/accounts/permissions.py` and `frontend/src/features/staff/roles.ts` must stay
identical. Reads need *view*, writes need *edit*.

| Role | overview | alerts | emergencies | beds | blood | donors | pharmacy | hospitals | specialists | users | equipment | operatingRooms | orBookings | transfers | ambulances | commandCentre | audit | reports | simulation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| admin | view | view | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | view | view | view | edit¹ |
| doctor | view | view | edit | view | view | – | view | view | view | – | view | view | edit | edit | view | – | – | – | – |
| nurse | view | view | edit | edit | – | – | view | view | edit | – | edit | edit | edit | edit | edit | – | – | – | – |
| bloodBank | view | view | view | – | edit | edit | – | view | view | – | – | – | – | edit | – | – | – | – | – |
| pharmacist | view | view | view | – | – | – | edit | view | view | – | – | – | – | – | – | – | – | – | – |
| patient | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – |

`emergencies` was added in Sprint 7 with #30 (see [api.md](api.md#emergency-cases-30-32)). `transfers` was added with
B01 (#47): it lets a role use the transfer endpoints at all. Who may ask, approve, ship or receive is narrowed per move
(see [transfers](api.md#transfers-47-48-49)). `specialists` was added with B16 (#61, #62): every staff role reads the
whole network, a nurse edits her own hospital only, and an admin edits any hospital (see
[specialists](#specialists-61-62)).

`ambulances` (B04, #50) is the ambulance registry: admin and nurse edit, doctor views. Blood bank and pharmacist have no access (see [ambulances](api.md#ambulances-b04-50)).
Trips (B05, #51) add two endpoints under it: `POST /transfers/<id>/trips/` and `POST /trips/<id>/actions/`. They need edit on
`ambulances` at the supplying hospital, so the receiving hospital's staff (and blood bank, which has no `ambulances` access)
can't send or step a trip. Trips add no module (see [trips](api.md#trips-b05-51)).

`orBookings` (story #29) is the module for booking and cancelling operating room slots. It has no nav item of its own: the day schedule is part of operating rooms.

`commandCentre` (story #55) is the city-wide figures page. Admins only, and view only: nobody can change anything through it. The page's
endpoint is in [api.md](api.md#city-command-centre-55).

`audit` (#56) is the audit trail: admins only, and read only (`view`). Its endpoints are in [api.md](api.md#audit-trail-56).

`simulation` (B21) is the live city simulation's panel: the city clock, scenarios and a mass-casualty event. ¹ Only the
**CityCare admin**, an admin with no hospital (`IsNetworkAdmin`); a hospital's admin has the module but is refused (403)
and doesn't see it in the menu (`canOpen` in `roles.ts`). Its endpoints are in
[api.md](api.md#live-city-simulation-b21).

`reports` (B18, #66, #67) is the operational reports page and its CSV/PDF export: admins only ("management" is the admin
role), read only (`view`). Its endpoints are in [api.md](api.md#operational-reports-b18-66-67).

`alerts` (B07, #53) is the Alerts page: every staff role views it. It lists only the user's own notifications, so nobody edits
through it. The endpoints stay on `IsStaff` (`apps/accounts/permissions.py`), so patients and signed-out users get 403 (see
[api.md](api.md#notifications-52)).

`donors` (B11) covers the donor endpoints: names, phones and emails, screening and donation appointments. Only admin and blood bank may use it, so doctors, nurses and pharmacists get **403** there (they can still read blood units). It has its own nav item, **Donors**.

**Own hospital only:** a user who isn't an admin may change a resource only if it belongs to their own
hospital (`resource.hospital == user.hospital`). A resource at another hospital is **404**, as if it didn't exist,
and that now holds on the blood screening, test, action and cancel endpoints and the bed action (B13, F3). A
refusal the service makes for another reason is still **403**. Admins manage the whole network.
The bed board (`GET /beds/`) and blood list (`GET /blood/units/`) only return the user's hospital when they
have one. Pharmacy has no hospital yet.

`User` (from `/auth/me/`, `/auth/login/`) gains `hospital: {id, name} | null`.

## Users (story 1.2 Role management)

| Method | Path | Access | Body | Success |
|---|---|---|---|---|
| GET | `/users/` | users: view | – | 200 `UserSummary[]`, sorted by email |
| PATCH | `/users/<id>/` | users: edit | `{role, hospitalId?}` | 200 `UserSummary` |

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
- `hospitalId` (optional) sets the hospital the user works at: left out keeps it, `null` clears it. Only an active
  hospital can be chosen: 400 `{hospitalId: [...]}` otherwise.
- 400 `{hospitalId: ["Choose the hospital this person works at."]}` when the result would be a doctor, nurse, blood bank
  or pharmacist with no hospital. Such an account could neither see nor change any hospital's records. Admins may
  have none, and then see the whole network (functional sweep, 22 Nov: F11 and F12 in the security review).
- Every change writes an audit entry `user.role_changed` with what changed before and after: `{role}`, `{hospital}`
  (by name) or both.
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
`bed.status_changed`, and answers 404 for a bed in another hospital (non-admins; B13, F3).

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
- **Public page.** Each hospital's public page (`/public/hospitals/<id>/`, B19) lists the specialists on call now by
  specialty and count; names only for signed-in hospital staff.
- **Audit:** `specialist.created` (after: name, specialty, hospital), `specialist.updated` (only the fields that changed,
  before and after), `on_call.created` (after: startsAt, endsAt) and `on_call.deleted` (before: startsAt, endsAt). The
  target of an `on_call` entry is the window.
- **Admin:** read-only, the same as transfers, so every change goes through the app and is audit-logged.

## Audit (story 8.1)

Entries are append-only (the model refuses update and delete), so the API can neither edit nor delete them. Admins
search and export them with `GET /api/audit/entries/` and `GET /api/audit/entries/export/` (issue #56, see
[api.md](api.md#audit-trail-56)). Django admin stays read-only as well (`/admin/audit/auditlog/`).

## Patient transfers (B17, #63 to #65)

No new module and no change to `ACCESS`: the endpoints use `emergencies`. Who may do what is narrowed per move, as
[api.md](api.md#patient-transfers-63-to-65) describes. Shapes are in `frontend/src/api/emergencies.ts`.

| Action | Path | Module | Object rule | Refused |
|---|---|---|---|---|
| Read the list | `GET /patient-transfers/` | emergencies: view | Your hospital receives the patient (incoming) or sends it (outgoing). Admins: all | 403 for a patient |
| Ask | `POST /emergencies/<reference>/patient-transfer/` | emergencies: edit | The case's hospital. Admins: any | 403 without edit on emergencies; 404 for a case you can't see |
| Confirm arrival | `POST /patient-transfers/<id>/actions/` `arrive` | emergencies: edit | The receiving hospital. Admins: any | 403 at the sending hospital; 404 at neither |
| Cancel | `POST /patient-transfers/<id>/actions/` `cancel` | emergencies: edit | The sending hospital. Admins: any | 403 at the receiving hospital; 404 at neither |
