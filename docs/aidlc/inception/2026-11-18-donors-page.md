# Inception Spec: Donors page

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B11](../bolts/B11-donors-page.md)
**Related backlog items:** [#20](https://github.com/harishassan-code/hospital-care/issues/20) Donor registration,
[#21](https://github.com/harishassan-code/hospital-care/issues/21) Donor eligibility screening,
[#22](https://github.com/harishassan-code/hospital-care/issues/22) Donation appointments (Sprint 8; the API shipped in Sprint 3)

## Problem

The donor API has been live since Sprint 3. It registers donors, records eligibility screening and books donation
appointments. Staff have no screen for any of it. `/staff/donors` still shows the "coming in Sprint 8" placeholder, so
donors can only be added or booked through the API.

This is for blood bank staff, who register donors and book appointments at their hospital, and for admins, who can act
for any hospital. Doctors, nurses and pharmacists don't need donor details.

The page uses the existing API as it is. The one required backend change is an access change. Today every role that can
read blood, doctors included, can read donor names, phones and emails. See Backend changes.

## User stories

- As blood bank staff, I want to search donors and register a new one, so that every donation has a donor with a code. (#20)
- As blood bank staff, I want to record whether a donor is eligible, with a reason and an end date, so that ineligible
  donors are not booked. (#21)
- As blood bank staff, I want to book a donation appointment on a free slot and cancel it, so that donors come in when
  the blood bank can take them. (#22)
- As an admin, I want the same page for every hospital, so that I can act for any hospital.

## Acceptance criteria

### Page and access

- [ ] `/staff/donors` opens a Donors page. It has its own **Donors** item in the staff menu, after **Blood bank**.
- [ ] Admin and blood bank staff can use every part of the page.
- [ ] Doctor, nurse and pharmacist don't see the menu item. Opening the URL shows the existing access-denied screen.
- [ ] The `/staff/donors` entry is removed from `frontend/src/features/staff/planned.ts`.

### Donor list and search (#20)

- [ ] The list shows the donors the user can see, with code, name, blood group, last donation date (or "None yet") and
  eligibility. It does not show phone or email.
- [ ] A search box matches name, code or phone. A blood group filter has an "All groups" choice. Results update when
  typing pauses for about 300 ms, and when a filter changes.
- [ ] When the API returns 200 donors, the list says "Showing the first 200 matches. Narrow the search to see the rest."
- [ ] With no donors yet, the list says "No donors registered at your hospital yet." With no match, it says "No donors
  match this search."
- [ ] If the list can't load, the page shows "Couldn’t load donors." and a **Try again** button.
- [ ] Choosing a donor opens the donor panel on the same page. The chosen code is kept in `?donor=`, so a reload keeps it.

### Register a donor (#20)

- [ ] Fields: full name (required, up to 150 characters), blood group (required, one of the eight groups), phone
  (optional) and email (optional).
- [ ] Before sending, the page checks what the API checks. Name is present and at most 150 characters. Phone is 7 to 20
  characters: digits, spaces, dashes and an optional leading `+`. Email has an `@` and a domain, if given.
- [ ] An error shows under its field, and focus moves to the first invalid field. The form keeps what was typed.
- [ ] On success the new donor opens in the donor panel, and a status message says "Donor DNR-00042 registered." The
  code comes from the server. A new donor shows as eligible.
- [ ] Errors: 400 shows the server's message under the field. 403 shows "Your role can’t register donors." Any other
  failure shows "The hospital’s system didn’t respond, so the donor wasn’t registered. Try again."

### Donor panel and eligibility (#21)

- [ ] The panel shows code, name, blood group, phone, email, last donation, and one eligibility status: "Eligible",
  "Not eligible until 12 Dec 2026" or "Not eligible, no end date". Non-eligible statuses show the reason.
- [ ] The panel lists the donor's units (ID, component, status). Read only.
- [ ] Screening form: **Eligible** or **Not eligible**, one must be chosen. For not eligible, a reason is required (up to
  300 characters). Then either an end date, which must be after today, or a **No end date** checkbox for a permanent
  deferral. The page checks these before sending.
- [ ] Saving "Eligible" clears the deferral. The panel and the list row update from the server's response.
- [ ] Screening errors show as in the registration form. 403 shows "Your role can’t screen donors."

### Appointments (#22)

- [ ] The panel lists the donor's upcoming booked appointments, each with a **Cancel** button.
- [ ] To book, the user picks a day (not in the past) and a start time. Start times run from 08:00 to 17:00, every 30
  minutes. Each time is a button whose text includes its state.
- [ ] A time is disabled and labelled "Booked" when the hospital already has a booked appointment at that time. Times
  that have passed are disabled.
- [ ] Days before the donor's `eligibleFrom` are disabled. A permanent deferral shows "This donor can’t be booked." and no
  times.
- [ ] A donor with an upcoming appointment can't book another. The book control is disabled, and the text gives the date
  and time of that appointment.
- [ ] After booking, the appointment appears in the list. A status message says "Booked DNR-00042 for 12 Dec 2026, 10:00."
- [ ] If the server refuses a time because someone else booked it first, the page shows the server's message and reloads
  the day's bookings.
- [ ] **Cancel** asks for confirmation (**Confirm cancel** or **Keep it**). On success the row leaves the upcoming list
  and the time can be booked again. A 409 ("already cancelled") shows its message and reloads the list.
- [ ] With no upcoming appointments, the panel says "No upcoming appointments for this donor."

### Loading and errors

- [ ] While data loads, the page shows "Loading donors…" as a status message.
- [ ] A failed panel load shows its own message and does not hide the rest of the page.

### Accessibility

- [ ] Every field has a visible label. Required fields say "Required" in text, not only with colour or an asterisk.
- [ ] Errors are text next to their field, linked to it, and announced (`role="alert"` or a live region).
- [ ] Eligibility and appointment states use text as well as colour.
- [ ] Every action works with the keyboard alone, and the focus ring is visible.
- [ ] The donor list is a real table with header cells. Each row has a button with the donor's name that opens the panel.
- [ ] Each slot button includes its time and state in its accessible name ("10:00, booked").

## The rules in one place

| Thing | Rule |
|---|---|
| Donor code | `DNR-` and five digits. The server sets it (next free number). The page never sets one. |
| Donor fields | Full name required, up to 150 characters. Blood group: one of the eight. Phone and email optional. Phone: 7 to 20 characters of digits, spaces, dashes and an optional leading `+`. |
| Hospital | A donor belongs to the hospital of the staff member who registered them. Staff see their hospital's donors; admins see all. |
| Eligibility | Worked out when read. Not eligible while a deferral is open (a reason is set, and there is no end date or the end date is after today), or while the last donation is less than `BLOOD_MIN_DONATION_INTERVAL_DAYS` (56) days ago. `eligibleFrom` is the first day they can give again. |
| Screening | Not eligible needs a reason (up to 300 characters). An end date must be after today. No end date means a permanent deferral. Eligible clears the deferral. |
| Appointment start | On a `BLOOD_APPOINTMENT_SLOT_MINUTES` (30) boundary, in the future. The server checks the time in `Asia/Karachi` (its `TIME_ZONE`). The page assumes the browser is in that zone. |
| Appointment donor | Eligible on the day of the slot, and no other upcoming booked appointment. |
| One booking per slot | One booked appointment per hospital per start time (the database enforces it). A cancelled slot is free again. |
| Cancel | Only a booked appointment can be cancelled. A second cancel is 409. |
| Search | Name contains the text, phone contains the text, code matches exactly. Blood group matches exactly. At most 200 rows. |
| Access | New `donors` module: admin and blood bank have edit. Admin acts for any hospital. Doctor, nurse and pharmacist have none. |
| Personal data | Phone and email appear only in the donor panel. Not in the list, not in the URL (the code is used), not in browser storage. Screening reasons go to the audit log, so keep them short and free of names. Demo donors are synthetic. |
| Audit | Written by the API: `donor.registered` (code and group only), `donor.screened`, `appointment.booked`, `appointment.cancelled`. The page adds nothing. |

## Endpoints the page calls

| Action | Call | Access | Notes |
|---|---|---|---|
| Load and search donors | `GET /api/blood/donors/?q=&bloodGroup=` | donors: view | At most 200 rows. Name, code, group and eligibility are shown; phone and email are not in the list. |
| Register a donor | `POST /api/blood/donors/` `{fullName, bloodGroup, phone?, email?}` | donors: edit | 201, returns the donor with its code. |
| Donor panel | `GET /api/blood/donors/<code>/` | donors: view | Donor plus `units`. |
| Record screening | `POST /api/blood/donors/<code>/screening/` `{eligible, reason?, deferredUntil?}` | donors: edit | 200, returns the donor. |
| Upcoming appointments | `GET /api/blood/appointments/` | donors: view | Booked, upcoming, at the user's hospital. The page filters by `donorId` for the donor panel, and reads the booked times of the chosen day for taken slots. |
| Book | `POST /api/blood/appointments/` `{donorId, startsAt}` | donors: edit | 201. |
| Cancel | `POST /api/blood/appointments/<id>/cancel/` | donors: edit | 200. 409 if already cancelled. |

No new endpoint is needed. Free slots come from the booked appointments the list already returns.

## Backend changes

Change 1 is required. Changes 2 to 5 are small. Drop any of them if the Product Owner prefers.

1. **Access.** Add a `donors` module to `ACCESS` in `backend/apps/accounts/permissions.py` (admin and bloodBank: edit,
   nobody else), and the same entry in `frontend/src/features/staff/roles.ts`. Add a `donors` column to the table in
   `docs/architecture/api-contracts.md`.
2. **Views.** In `backend/apps/blood/views.py`, `DonorListView`, `DonorDetailView`, `DonorScreeningView`,
   `AppointmentListView` and `AppointmentCancelView` use `module_permission("donors")` instead of `BloodAccess`. The unit
   views keep `blood`.
3. **Booking across hospitals.** `book_appointment` in `backend/apps/blood/services.py` refuses a donor the actor may not
   change (403, using `may_change`). Today the API accepts any donor code. The page never offers one, so this closes a gap
   that only an API caller can reach.
4. **Tests.** In `backend/apps/blood/tests/test_donors.py`: doctor and nurse get 403 on the donor endpoints, blood bank gets
   200, and booking a donor from another hospital gets 403.
5. **Docstring.** The `AppointmentListView` docstring mentions `?from=YYYY-MM-DD`, which the code does not implement.
   Remove it.

## Non-goals

- Editing a donor's details after registration. The API has no edit endpoint.
- Deleting donors or appointments. A wrong appointment is cancelled. A wrong deferral is changed with a new screening.
- Moving an appointment. Cancel it and book again.
- Recording a donation. Units are registered on the Blood page. Linking a unit to a donor from the unit form is not in
  this bolt.
- A duplicate check when registering (same name and phone). Staff search first.
- Consent to contact donors or to test them. The API has no field for it. This needs a Product Owner decision first.
- Reminders to donors by SMS or email. That is notifications (B06, B07).
- Opening hours per hospital, or a slot length per hospital. The API has neither.
- A hospital picker for admins. An admin with no hospital registers a donor with no hospital, and only admins can see
  that donor. Blood units already work this way.
- Import, export, and paging beyond 200 rows.
- Booking by donors themselves. Only staff book.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Separate nav item, or a tab inside Blood bank?** Proposed: a separate **Donors** item at `/staff/donors`. Reason:
   donors get their own access module (question 2), and the Blood page is already long.
2. **Who can see donors?** Proposed: a new `donors` module, edit for admin and blood bank, and nothing for doctor, nurse
   or pharmacist. Reason: donor names, phones and emails are personal data, and the blood module lets doctors read them
   today. No page calls the donor endpoints yet, so nothing breaks.
3. **Which times can a donor be booked at?** Proposed: the page offers start times from 08:00 to 17:00, and the server
   keeps accepting any 30-minute boundary. Reason: the API has no opening hours. A fixed window on the page stops odd
   times without a new server rule. The Product Owner can change the window.
4. **How long is a slot on the page?** Proposed: 30 minutes, as a constant in the page that mirrors
   `BLOOD_APPOINTMENT_SLOT_MINUTES`, the way `shelfLifeDays` mirrors the backend in `frontend/src/api/blood.ts`. Reason:
   the slot length only comes back once an appointment exists, so the page can't read it first.
5. **Can staff book a donor from another hospital?** Proposed: no. Add the check in Backend change 3. Reason: the API
   accepts any donor code, and the booking is recorded at the staff member's hospital.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
