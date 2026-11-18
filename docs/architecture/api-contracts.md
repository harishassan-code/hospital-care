# API contracts: Sprint 2

Agreed before building. The frontend tests mock exactly these shapes (`frontend/src/test/mockApi.ts`), and the
backend tests check them. The Sprint 1 endpoints are in [api.md](api.md). Same conventions apply: JSON, session
cookie + `X-CSRFToken` on writes, camelCase field names.

Common errors on every endpoint below: **403** when signed out or the role lacks access, **404** for an
unknown id, **400** `{field: ["message"]}` for invalid input.

## Access (stories 1.2)

`ACCESS` in `backend/apps/accounts/permissions.py` and `frontend/src/features/staff/roles.ts` must stay
identical. Reads need *view*, writes need *edit*.

| Role | overview | alerts | emergencies | beds | blood | donors | pharmacy | hospitals | users | equipment | operatingRooms | orBookings | transfers | ambulances | commandCentre | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| admin | view | view | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | view | view |
| doctor | view | view | edit | view | view | – | view | view | – | view | view | edit | edit | view | – | – |
| nurse | view | view | edit | edit | – | – | view | view | – | edit | edit | edit | edit | edit | – | – |
| bloodBank | view | view | view | – | edit | edit | – | view | – | – | – | – | edit | – | – | – |
| pharmacist | view | view | view | – | – | – | edit | view | – | – | – | – | – | – | – | – |
| patient | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – |

`emergencies` was added in Sprint 7 with #30 (see [api.md](api.md#emergency-cases-30-32)). `transfers` was added with
B01 (#47): it lets a role use the transfer endpoints at all. Who may ask, approve, ship or receive is narrowed per move
(see [transfers](api.md#transfers-47-48-49)).

`ambulances` (B04, #50) is the ambulance registry: admin and nurse edit, doctor views. Blood bank and pharmacist have no access (see [ambulances](api.md#ambulances-b04-50)).
Trips (B05, #51) add two endpoints under it: `POST /transfers/<id>/trips/` and `POST /trips/<id>/actions/`. They need edit on
`ambulances` at the supplying hospital, so the receiving hospital's staff (and blood bank, which has no `ambulances` access)
can't send or step a trip. Trips add no module (see [trips](api.md#trips-b05-51)).

`orBookings` (story #29) is the module for booking and cancelling operating room slots. It has no nav item of its own: the day schedule is part of operating rooms.

`commandCentre` (story #55) is the city-wide figures page. Admins only, and view only: nobody can change anything through it. The page's
endpoint is in [api.md](api.md#city-command-centre-55).

`audit` (#56) is the audit trail: admins only, and read only (`view`). Its endpoints are in [api.md](api.md#audit-trail-56).

`alerts` (B07, #53) is the Alerts page: every staff role views it. It lists only the user's own notifications, so nobody edits
through it. The endpoints stay on `IsStaff` (`apps/accounts/permissions.py`), so patients and signed-out users get 403 (see
[api.md](api.md#notifications-52)).

`donors` (B11) covers the donor endpoints: names, phones and emails, screening and donation appointments. Only admin and blood bank may use it, so doctors, nurses and pharmacists get **403** there (they can still read blood units). It has its own nav item, **Donors**.

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

## Audit (story 8.1)

Entries are append-only (the model refuses update and delete), so the API can neither edit nor delete them. Admins
search and export them with `GET /api/audit/entries/` and `GET /api/audit/entries/export/` (issue #56, see
[api.md](api.md#audit-trail-56)). Django admin stays read-only as well (`/admin/audit/auditlog/`).
