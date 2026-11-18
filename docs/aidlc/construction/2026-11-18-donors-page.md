# Construction Plan: Donors page

**Spec:** [docs/aidlc/inception/2026-11-18-donors-page.md](../inception/2026-11-18-donors-page.md)
**Bolt:** [B11](../bolts/B11-donors-page.md)
**Date:** 2026-11-18

The donor API (#20 to #22) already exists. This plan adds the access change, a refusal for cross-hospital booking, and
the Donors page on top of the existing endpoints. Units land in order on one branch, like the transfer bolts.

## Design

### Access (`backend/apps/accounts/permissions.py`, `frontend/src/features/staff/roles.ts`)

- New module `donors`: admin and bloodBank **edit**. Doctor, nurse, pharmacist and patient have no row entry.
- The same entry in both files, and a `donors` column in `docs/architecture/api-contracts.md`.

### Backend (`backend/apps/blood/`)

- `DonorListView`, `DonorDetailView`, `DonorScreeningView`, `AppointmentListView`, `AppointmentCancelView` use
  `module_permission("donors")`. The unit views keep `blood`.
- `services.book_appointment` first checks `may_change(actor, donor)` and raises `PermissionDenied` (403). It runs
  before the other checks, so a refused caller learns nothing about the donor's eligibility.
- Two read-only fields, `hospitalId`, on `DonorSerializer` and `AppointmentSerializer`. The page needs them to find the
  booked times that count for a slot (see Deviations).
- `AppointmentListView` docstring: drop the `?from=` mention the code never implemented.

### Frontend

- `src/api/donors.ts`: types (`Donor`, `DonorDetail`, `Appointment`), the calls, and `DONOR_SLOT_MINUTES = 30` mirroring
  `BLOOD_APPOINTMENT_SLOT_MINUTES`. Start times are `DONOR_FIRST_SLOT` (08:00) to `DONOR_LAST_SLOT` (17:00), inclusive.
- `src/features/donors/donors.ts`: pure helpers. Slot list, slot state, eligibility wording, date formatting.
- `src/features/donors/validation.ts`: register and screening checks, the same rules as the API, run before sending.
- `src/features/donors/`: `DonorTable`, `RegisterDonorForm`, `DonorPanel` (details, units, appointments),
  `ScreeningForm`, `BookAppointment`. Styles in `Donors.module.css`.
- `src/pages/staff/DonorsPage.tsx`: list, search (300 ms debounce) and blood group filter; `?donor=` opens the panel.
- `roles.ts` `donors` module, nav entry **Donors** after **Blood bank**, route `donors` in `App.tsx`, removed from
  `planned.ts`.
- `src/test/mockApi.ts` gets the donor and appointment routes (edit/view gated by `canEdit`/`canSee`, like the server).
  `src/test/fixtures/donors.ts` is synthetic (`example.com` emails, reserved-looking phone numbers, invented names).
- `components/form/Button` gets an optional `disabled` prop, so the book control can be disabled.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Access row, module on the five donor views, cross-hospital refusal, `hospitalId` fields, docstring | `accounts/permissions.py`, `blood/views.py`, `blood/services.py`, `blood/serializers.py` | `blood/tests/test_donors.py`: doctor, nurse, pharmacist 403; blood bank 200; other-hospital donor 403 on book, screen and cancel; admin books anywhere |
| 2 | Frontend access, nav, route, planned removal, mock routes and fixtures | `features/staff/roles.ts`, `planned.ts`, `App.tsx`, `test/mockApi.ts`, `test/fixtures/donors.ts`, `components/form/Button.tsx` | `roles.test.ts` (table and module list), `StaffLayout.test.tsx` (admin nav), `fixtures.test.ts` |
| 3 | API client and feature helpers: slots, eligibility wording, validation | `api/donors.ts`, `features/donors/donors.ts`, `features/donors/validation.ts` | `api/donors.test.ts`, `features/donors/donors.test.ts` |
| 4 | Donors page: list, search, filter, register form, donor panel, screening, booking, cancel | `pages/staff/DonorsPage.tsx`, `features/donors/*.tsx`, `Donors.module.css` | `pages/staff/DonorsPage.test.tsx` |
| 5 | QA smoke and docs | `qa/features.qa.test.tsx`, `docs/architecture/api.md`, `docs/architecture/api-contracts.md` | QA test additions; docs reviewed against the code |

## Sequencing

1 → 2 → 3 → 4 → 5. Unit 2's access rule must match unit 1's backend row; its frontend tests run against the mock.
Unit 4 depends on 2 and 3. Unit 5 last, so the docs describe the code that shipped.

## Test plan

- **Backend.** Each role against each donor endpoint (list, register, detail, screening, appointments list, book,
  cancel); doctor and nurse 403, blood bank 200. Booking a donor from another hospital, screening one and cancelling
  one: 403. Admin books for any hospital. Existing blood tests stay green; none asserted doctor access to donors, so
  none changed.
- **Frontend unit.** Slot list (19 times, 08:00 to 17:00); slot state (free, booked at this hospital, passed); eligibility
  wording for the three states; validation mirrors the API (name, group, phone regex, email, reason, end date).
- **Frontend page.** Search debounce and blood group filter; 200-row note; both empty states; list error and Try again;
  register validation with focus on the first invalid field and the form kept; server 400/403/other messages; donor
  panel by `?donor=` reload; screening validation and the list row update; booking states, disabled book control with
  the donor's appointment, "can't be booked" for permanent deferral, 409 reload, cancel confirm and 409 reload; a
  failed panel load does not hide the list.
- **QA.** Blood bank and admin see Donors; nurse, doctor and pharmacist don't; doctor opening `/staff/donors` gets the
  access-denied screen.
- **CI.** The three check commands in `AGENTS.md` (backend ruff, format, migrations check, pytest; frontend lint, test,
  build; root deploy config and board check).

## Deviations

- **`hospitalId` on donors and appointments (read-only).** The spec says a slot is taken when *the hospital* has a
  booking at that time. The list endpoint shows all hospitals to admins, so the page can't tell which bookings count
  without the hospital. The page uses the same rule as `book_appointment`: the actor's hospital, else the donor's.
- **Donor list includes `phone` and `email`.** The API sends them in the list (as before). The page never renders them
  in the list. Removing them from the list response would be a second access change; left for the Product Owner.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that approval
is the Construction gate.
