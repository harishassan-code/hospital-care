# API contracts: Sprint 2

Agreed before building. The frontend tests mock exactly these shapes (`frontend/src/test/mockApi.ts`), and the
backend tests check them. The Sprint 1 endpoints are in [api.md](api.md). Same conventions apply: JSON, session
cookie + `X-CSRFToken` on writes, camelCase field names.

Common errors on every endpoint below: **403** when signed out or the role lacks access, **404** for an
unknown id, **400** `{field: ["message"]}` for invalid input.

## Access (stories 1.2)

`ACCESS` in `backend/apps/accounts/permissions.py` and `frontend/src/features/staff/roles.ts` must stay
identical. Reads need *view*, writes need *edit*.

| Role | overview | emergencies | beds | blood | pharmacy | hospitals | users | equipment | operatingRooms | orBookings | transfers | ambulances | donors | alerts | commandCentre | audit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| admin | view | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | edit | view | view | view |
| doctor | view | edit | view | view | view | view | – | view | view | edit | edit | view | – | view | – | – |
| nurse | view | edit | edit | – | view | view | – | edit | edit | edit | edit | edit | – | view | – | – |
| bloodBank | view | view | – | edit | – | view | – | – | – | – | edit | – | edit | view | – | – |
| pharmacist | view | view | – | – | edit | view | – | – | – | – | – | – | – | view | – | – |
| patient | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – | – |

Sprint 8 added `ambulances` (B04/B05, #50 #51), `donors` (B11: a nav item only; the donor endpoints check `blood`),
`alerts` (B07: every staff role; the notification endpoints only need a staff sign-in), `commandCentre` (B09, #55)
and `audit` (B10, #56). Dispatching an ambulance uses the transfer's supplier-side rule.

`emergencies` was added in Sprint 7 with #30 (see [api.md](api.md#emergency-cases-30-32)). `transfers` was added with
B01 (#47): it lets a role use the transfer endpoints at all. Who may ask, approve, ship or receive is narrowed per move
(see [transfers](api.md#transfers-47-48-49)).

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

## Audit (stories 8.1, #56)

Entries are append-only (the model refuses update and delete). Admins search them with
`GET /api/audit/?actor=&action=&targetType=&targetId=&from=YYYY-MM-DD&to=YYYY-MM-DD&q=&page=` →
`{count, page, pageSize: 50, results: [{id, at, actor, action, targetType, targetId, target, reason, before, after}]}`
(newest first; `action` ending in `.` is a prefix, e.g. `transfer.`). `GET /api/audit/export.csv` with the same
filters streams CSV; each export is itself logged as `audit.exported`.

## Notifications (#52, #53)

Any staff role. `GET /api/notifications/?unread=1&critical=1` → the latest 50 `{id, kind, severity, title, body, link,
createdAt, read, acknowledged}` for the user's hospital and role (admins: every hospital).
`GET /api/notifications/unread-count/` → `{unread, critical}`. `POST /api/notifications/<id>/read/`,
`POST /api/notifications/read-all/` → `{marked}`, `POST /api/notifications/<id>/acknowledge/` (clears a critical
banner for that user). Events: `emergency.created`, `emergency.escalated`, `transfer.requested` (critical, to the
supplier's answering roles), `transfer.<status>` (to the other side), `reservation.expired`.

## Ambulances (#50, #51)

`GET /api/ambulances/?type=&status=&hospital=` (own hospital; admins all) → `[{id, identifier, type: bls|als|pts, plate, note, status: available|onTrip|maintenance|outOfService,
statusSince, hospital, hospitalId}]`. `POST` registers (ambulances: edit). `POST /api/ambulances/<id>/actions/`
`{action: startMaintenance|finishMaintenance|outOfService|returnToService}`; 409 if the lifecycle refuses.

`GET /api/ambulances/available/?hospital=` (transfers: view; non-admins get their own hospital) lists available
ambulances for the dispatch picker. `POST /api/ambulances/trips/ {transferId, ambulanceId}` dispatches an available ambulance of the supplier's fleet
with an approved transfer (the transfer goes to *dispatched*) → `{id, ambulance: {id, identifier}, status, etaMinutes,
dispatchedAt, arrivedAt}`; 409 if the ambulance isn't available or belongs elsewhere.
`POST /api/ambulances/trips/<id>/actions/ {action: enRoute|arrive}` (en route also moves the transfer to
*in transit*). Receipt completes the trip and frees the ambulance; cancelling the transfer cancels it. Each transfer
now has `trip` (or `null`).

## City command centre (#55)

`GET /api/command-centre/` (admin) → `{totals: {hospitals, freeBeds, freeIcu, redCells, nearExpiry,
activeEmergencies}, hospitals: [{id, name, beds: {free, total}, icu: {free, total}, redCells: {group: n}, nearExpiry,
equipment: {available, total}, emergencies: {severity: n}}], shortages: [{hospital, kind: blood|icu, level, group?,
count?, minimum?}]}`. A fixed number of queries however many hospitals there are.
