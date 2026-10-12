# API contracts: Sprint 2

Agreed before building. The frontend tests mock exactly these shapes (`frontend/src/test/mockApi.ts`), and the
backend tests check them. The Sprint 1 endpoints are in [api.md](api.md). Same conventions apply: JSON, session
cookie + `X-CSRFToken` on writes, camelCase field names.

Common errors on every endpoint below: **403** when signed out or the role lacks access, **404** for an
unknown id, **400** `{field: ["message"]}` for invalid input.

## Access (stories 1.2)

`ACCESS` in `backend/apps/accounts/permissions.py` and `frontend/src/features/staff/roles.ts` must stay
identical. Reads need *view*, writes need *edit*.

| Role | overview | beds | blood | pharmacy | hospitals | users |
|---|---|---|---|---|---|---|
| admin | view | edit | edit | edit | edit | edit |
| doctor | view | view | view | view | view | – |
| nurse | view | edit | – | view | view | – |
| bloodBank | view | – | edit | – | view | – |
| pharmacist | view | – | – | edit | view | – |
| patient | – | – | – | – | – | – |

**Own hospital only:** a user who isn't an admin may change a resource only if it belongs to their own
hospital (`resource.hospital == user.hospital`); otherwise **403**. Admins manage the whole network.
Reads of a module are limited to the user's hospital when they have one.

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

## Resource status (task 2.0)

There's no new endpoint. `POST /beds/<id>/actions/` now runs through the shared state machine
(`apps/resources`). It records who, when, from, to and why in `StatusChange`, writes the audit entry
`bed.status_changed`, and answers 403 for a bed in another hospital (non-admins).

## Audit (story 8.1)

There's no endpoint in Sprint 2. Entries are append-only (the model refuses update and delete), so the API can
neither edit nor delete them. Admins read them in Django admin (`/admin/audit/auditlog/`, read-only). Search and
export come with issue #56 in Sprint 8.
