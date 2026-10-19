# Backend API (Sprint 1)

Sprint 2 endpoints (users, hospitals, structure) are in [api-contracts.md](api-contracts.md).

Base URL: `http://localhost:8000/api` locally. All bodies are JSON. Field names match the TypeScript types in
`frontend/src/api/`, so each frontend `get…()` function can switch from sample data to the real call unchanged.

## Auth (session cookie + CSRF)

The browser keeps a Django session cookie. Every request must use `credentials: 'include'` (the shared client
already does). Signed-in `POST`s must send the `X-CSRFToken` header from the `csrftoken` cookie (the client
already does); the cookie is set by `login`, `signup`, `me` and `csrf`.

| Method | Path | Who | Body | Success | Errors |
|---|---|---|---|---|---|
| GET | `/auth/csrf/` | anyone | – | 200, sets `csrftoken` cookie | – |
| POST | `/auth/login/` | anyone | `{email, password}` | 200 `User` | 400 bad input (email > 254 or password > 512 characters), 401 wrong email/password (same message for both), 429 after 5 failed attempts on the account (locked 15 min) |
| POST | `/auth/logout/` | anyone | – | 204 | 403 if CSRF header missing |
| POST | `/auth/signup/` | anyone | `{full_name, email, phone?, password}` | 201 `User` (always a patient) | 400 `{email: [...]}` taken, 400 `{password: [...]}` weak |
| GET | `/auth/me/` | signed in | – | 200 `User` | 403 when signed out |

`User` = `{id, email, fullName, phone, role, isStaff}`; `role` is one of `admin`, `doctor`, `nurse`,
`bloodBank`, `pharmacist`, `patient` (same ids as `features/staff/roles.ts`). Staff accounts are created in
Django admin, never through sign-up.

## Modules

Access follows `ACCESS` in `features/staff/roles.ts` (enforced in `apps/accounts/permissions.py`):
reading needs *view*, changing needs *edit*. No access → 403.

| Method | Path | Returns | Access |
|---|---|---|---|
| GET | `/public/status/` | `PublicStatus` (ER status + today's doctors) | anyone, no sign-in |
| GET | `/beds/` | `BedBoard` = `{wards, beds}` | beds: view |
| POST | `/beds/<bed id>/actions/` | `{action}` → updated `Bed` | beds: edit |
| GET | `/blood/units/` | `BloodUnit[]` | blood: view |
| GET | `/pharmacy/stock/` | `Medicine[]` with `batches` | pharmacy: view |

Bed actions: `discharge`, `markReady`, `reserve`, `cancelReservation`, `outOfService`, `returnToService`.
A move the bed lifecycle doesn't allow (e.g. reserving an occupied bed) returns **409** and changes nothing.
Unknown action → 400, unknown bed → 404. Discharging clears the patient details.

A blood unit past its expiry date is reported as `expired` (unless already `issued`), even if nobody has
updated its stored status yet.

## Blood bank (Sprint 3)

Every endpoint needs **blood: view** to read and **blood: edit** to change (admin, bloodBank). Staff only see and
change their own hospital's units, donors and appointments (**403** otherwise). Every change is audit-logged.

| Method | Path | Body | Success | Story |
|---|---|---|---|---|
| GET | `/blood/units/?status=&group=&component=` | – | `BloodUnit[]`; `status=available` never returns expired units | #18 |
| POST | `/blood/units/` | `{id, group, component, collectedAt, expiresAt?, location, donorId?}` | 201 `BloodUnit` | #17, #20 |
| GET | `/blood/units/<id>/` | – | `BloodUnitDetail` | #18 |
| POST | `/blood/units/<id>/tests/` | `{test, passed, reason?}` | 201 `BloodUnitDetail` | #18 |
| POST | `/blood/units/<id>/actions/` | `{action, reason?}` | 200 `BloodUnitDetail` | #18 |
| GET | `/blood/stock/?nearExpiryDays=3` | – | `BloodStock` | #19 |
| GET | `/blood/donors/?q=&bloodGroup=` | – | `Donor[]` (search by name, code or phone) | #20 |
| POST | `/blood/donors/` | `{fullName, bloodGroup, phone?, email?}` | 201 `Donor` (code `DNR-00001`, …) | #20 |
| GET | `/blood/donors/<id>/` | – | `Donor` + `units: BloodUnit[]` | #20 |
| POST | `/blood/donors/<id>/screening/` | `{eligible, reason?, deferredUntil?}` | 200 `Donor` | #21 |
| GET | `/blood/appointments/` (`?all=true` for past and cancelled) | – | `Appointment[]`, upcoming booked | #22 |
| POST | `/blood/appointments/` | `{donorId, startsAt}` | 201 `Appointment` | #22 |
| POST | `/blood/appointments/<id>/cancel/` | – | 200 `Appointment` | #22 |

```ts
BloodUnitDetail = BloodUnit & {
  donorId: string | null,
  tests: { test: Test, passed: boolean, reason: string, recordedAt: string }[],
  missingTests: Test[]          // tests still needed before release
}
Test = 'hiv' | 'hbv' | 'hcv' | 'syphilis' | 'malaria'
BloodStock = {
  nearExpiryDays: number, lowStockUnits: number,
  rows: { group, component, available, reserved, quarantined, nearExpiry: number, low: boolean }[],  // 8 groups × 4 components
  nearExpiryUnits: BloodUnit[]  // available units expiring within nearExpiryDays, soonest first
}
Donor = {
  id: string, fullName: string, bloodGroup: string, phone: string, email: string,
  lastDonationAt: string | null,
  eligible: boolean, ineligibleReason: string, eligibleFrom: string | null  // null + ineligible = permanent
}
Appointment = { id: number, donorId: string, donorName: string, startsAt: string, slotMinutes: number,
                status: 'booked' | 'cancelled' }
```

**Rules**

- **Screening (#18):** new units are `quarantined`. Each test is recorded once (repeat → 400). When all five have
  passed, the unit moves to `available` by itself. A failed test needs a `reason` and moves the unit to
  `discarded`. Tests on a unit that isn't quarantined → 409.
- **Unit actions:** `reserve`, `cancelReservation`, `issue`, `expire`, `release` (409 unless every test passed),
  `discard` (400 without a reason). A move the lifecycle doesn't allow → 409.
- **Expiry (#19):** units past their expiry date are marked `expired` (audit-logged, actor "system") by
  `python manage.py expire_blood_units` (schedule it hourly) and every time the stock view loads.
- **Stock (#19):** only `available` units count. `low` is true below `BLOOD_LOW_STOCK_UNITS` (default 5).
  `nearExpiryDays` defaults to `BLOOD_NEAR_EXPIRY_DAYS` (3); 0–60, otherwise 400.
- **Donors (#20):** synthetic identities only. A unit's group must match its donor's group (400 on `donorId`).
- **Eligibility (#21):** a donor can't give again within `BLOOD_MIN_DONATION_INTERVAL_DAYS` (56). Units collected
  the same day count as one donation (components). Screening `{eligible: false}` needs a reason; no
  `deferredUntil` means a permanent deferral. `{eligible: true}` clears it.
- **Appointments (#22):** on a `BLOOD_APPOINTMENT_SLOT_MINUTES` (30) boundary, in the future. One booked donor
  per hospital per slot (the database enforces it, so two people booking at once can't both win → 400).
  Ineligible donors and donors who already have an upcoming appointment → 400. A cancelled slot can be rebooked.

All four `BLOOD_*` settings can be changed with environment variables of the same name.

## Demo data

```bash
docker compose exec backend python manage.py seed_demo          # safe to re-run
docker compose exec backend python manage.py seed_demo --reset  # start the demo data over
```

Creates 3 hospitals (CityCare General, Seaview, Northside Children's) with 10 departments, 12 wards / 164 beds
(ICU, emergency, general, isolation and NICU) and 10 storage locations, plus 320 blood units (with screening results), 60 synthetic donors (two deferred) and 6 upcoming donation
appointments, 23 medicines, 14 doctor shifts, the ER status, and one login per
role (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`, `patient@demo.citycare.pk`, password
`CityCare-demo-1`). Demo only: never run it against real data.
