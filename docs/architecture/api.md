# Backend API (Sprint 1)

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

## Demo data

```bash
docker compose exec backend python manage.py seed_demo          # safe to re-run
docker compose exec backend python manage.py seed_demo --reset  # start the demo data over
```

Creates 7 wards / 106 beds, 320 blood units, 23 medicines, 14 doctor shifts, the ER status, and one login per
role (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`, `patient@demo.citycare.pk`, password
`CityCare-demo-1`). Demo only: never run it against real data.
