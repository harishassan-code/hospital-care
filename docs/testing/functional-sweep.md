# Functional sweep: every page and every form, as every role

**Date:** 22 Nov 2026 · **Build:** `main` after #125 · **Data:** a fresh `seed_demo` database (synthetic)

Before staging, the whole app was driven in a real browser (Chromium, Playwright) against the real API, to check that
every module works and that the frontend and backend agree. The unit tests run each side against a mock of the other,
and the [MVP scenario](mvp-scenario.md) covers one path through the core flow; this sweep covers the rest.

## 1. Every page, as every role

Each of the six demo logins opened every page in its menu, at desktop width (1366 px) and phone width (390 px), plus
every staff page outside its menu and the detail pages reached from the lists (a hospital, a specialist, a case). For
each page the run recorded console errors, page errors, API calls answered 4xx or 5xx, error messages on the page,
pages wider than the screen, and a page with no heading.

| Role | Pages in the menu | Result |
|---|---|---|
| Admin | 17 | No errors |
| Doctor | 12 | No errors |
| Nurse | 11 | No errors |
| Blood bank | 8 | No errors |
| Pharmacist | 6 | No errors |
| Patient | public pages only (lands on the home page) | No errors |
| Signed out | home, sign-in, sign-up, a missing page | No errors |

- **Pages outside a role's menu** show "You don't have access to this page" and load no data.
- **No page is wider than a phone screen.**
- **The only console message** is the 403 a signed-out visitor's browser logs for `GET /api/auth/me/`. That is how
  the app asks "am I signed in?"; it isn't an error.

## 2. Every form and action, against the real API

Each step drove the real form or button and checked every write request's status.

| Module | Role | What was done | Result |
|---|---|---|---|
| Sign-up | visitor | Create an account (terms ticked) | 201 |
| Users | admin | Give the new account a role (and, after the fix below, a hospital) | 200 |
| Users | new staff | Sign in to the staff workspace | 200 |
| Hospitals | admin | Register a hospital; add a department, ward and storage location; remove the location; edit it | 201, 204, 200 |
| Specialists | admin | Add a specialist; add and remove an on-call time; edit | 201, 204, 200 |
| Ambulances | admin | Register an ambulance; start and finish maintenance | 201, 200 |
| Reports | admin | Show a report; export CSV and PDF | files of 1.2 kB and 3.4 kB |
| Audit log | admin | Export CSV | 3.1 kB |
| Beds | nurse | Discharge a patient; mark the bed ready | 200 |
| Equipment | nurse | Register equipment; start and finish maintenance | 201, 200 |
| Alerts | nurse | Mark the new-case alert read | 200 |
| Operating rooms | doctor | Book a slot (a clash is refused with the existing booking named); cancel it | 400 then 201, 200 |
| Emergencies | doctor | Open a case with the three-step form (5 beds a line at most is enforced); escalate; cancel | 201, 200 |
| Emergencies | doctor | Request blood (quick form) | 201 |
| Patient transfer | doctor | Ask to move a patient short of ICU beds to Seaview, the nearest with free beds | 201 |
| Patient transfer | admin | Confirm arrival for Seaview (after the fix below) | 200 |
| Stock transfer | doctor, admin | Request O− units from Seaview; approve | 201, 200 |
| Ambulance trip | admin | Dispatch an ambulance for the transfer; departed, arrived, completed | 201, 200 ×3 |
| Blood bank | blood bank | Register a unit; pass its four remaining tests (it is released) | 201 ×5 |
| Donors | blood bank | Register a donor; record a screening; book an appointment; cancel it | 201, 200, 201, 200 |

Together with the MVP scenario (case, holds, competing case, transfer through delivery, allocation, closing, audit
search), every write endpoint the frontend calls was exercised: 64 of the 66 API routes have a caller in the frontend.
The other two are `/api/health/` (for Render) and `/api/blood/stock/`, whose numbers the Blood page works out from
the unit list.

## 3. What it found, and what changed

| # | Found | Fix |
|---|---|---|
| F11 | A staff account without a hospital saw **every hospital's records** (beds, blood, cases, stock). It could not change them. | `own_hospital()` gives the network only to admins. [Security review](security-review.md), F11 |
| F12 | There was **no way to give a user a hospital**: the Users page and `PATCH /api/users/<id>/` changed the role only, and the Django admin is off on staging. So the only way to add staff on staging produced the F11 account. | The Users page has a hospital picker; the API takes `hospitalId` and refuses a doctor, nurse, blood bank or pharmacist without one. Security review, F12 |
| – | A patient transfer could be asked for but **never completed in the demo**: arrival is confirmed at the receiving hospital, the demo has no logins there, and the admin's list of outgoing patients had no button, though the API lets admins confirm. | Outgoing patients shows **Confirm arrival at …** when the API lists `arrive` for the user (admins), as the admin already acts for the partner hospitals on stock transfers |

Checked and **not** a gap:

- After **Open case** the app stays on the list with "Case EC-… is open" and a link, rather than opening the case.
- A blood unit can be **discarded only from quarantine** (a failed test) and **issued through a case**. The lifecycle
  (`BLOOD_UNIT_LIFECYCLE`) has no other discard or issue, so the UI is complete for it. Discarding damaged stock with a
  reason is in the [roadmap](../deliverables/handover-and-roadmap.md) ("wastage reason codes").

## 4. Rerunning it

The sweep scripts are throwaway Playwright programs and are not in the repo. The MVP scenario (`e2e/`) is the
repeatable part, and runs in CI. To repeat the sweep by hand: start the app on a fresh database (README), then, as each
demo login, open every menu entry and use each form in the table above.
