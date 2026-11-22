# User acceptance test (UAT) checklist: MVP

**For:** the Product Owner, on staging after `seed_demo` (synthetic data only).
**Automated companion:** the end-to-end scenario in `e2e/tests/mvp-scenario.spec.ts` (bolt B12, #57; see
`docs/testing/mvp-scenario.md`) runs the core flow in CI. This checklist covers each story by hand.

**Logins** (password `CityCare-demo-1` for all): `admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`,
`patient@demo.citycare.pk` (CityCare General Hospital). There is no login at the other hospitals, so `admin@` acts
for the supplying hospital in transfer rows, as the automated scenario does (`docs/testing/mvp-scenario.md`).

Mark each row **Pass** or **Fail** and add notes for anything that fails. A failed row becomes a new issue.

## Accounts, roles and hospitals

| # | Story | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|
| 1 | #7 #8 Sign-in and session | Log in as `doctor@`, reload, sign out; try a wrong password | Lands on /staff; stays signed in on reload; sign-out returns to login; wrong password shows an error | | |
| 2 | #73 Patient sign-up | /signup with a new email | Account created; patient lands outside the staff area | | |
| 3 | #9 #10 Roles and access | Log in as each role; compare the sidebar with the access table in `docs/architecture/api-contracts.md` | Each role sees only its modules; opening a hidden module's URL shows "no access" | | |
| 4 | #11–#13 Hospitals | As admin: Hospitals → register a hospital, add a ward, set capabilities | Saved and listed; doctor can view but not edit | | |
| 5 | #15 Audit logging | After rows 4 and 8, as admin open Audit log | Each change is there with actor, time, before/after | | |

## Inventory

| # | Story | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|
| 6 | #17–#19 Blood units | As `bloodbank@`: register a unit, record tests, check the stock grid | Unit appears; quarantined until tests pass; low/near-expiry warnings show | | |
| 7 | #20–#22 Donors (B11) | As `bloodbank@`: Donors → register a donor, record a deferral, book and cancel an appointment for an eligible donor | Donor code shown; eligibility changes; appointment listed then removed | | |
| 8 | #23–#25 Beds | As `nurse@`: Beds → change a bed's status | Board updates; occupancy figures change | | |
| 9 | #26 #27 Equipment | As `nurse@`: Equipment → register, start maintenance | Listed; status changes; doctor is read-only | | |
| 10 | #28 #29 Operating rooms | As `nurse@`/`doctor@`: book a slot, cancel it | Booking on the schedule, then gone | | |
| 11 | #50 Ambulances (B04) | As `nurse@`: Ambulances → register `AMB-TEST-01`, start and finish maintenance | Listed with base and type; status follows; doctor read-only | | |

## Emergencies, matching and transfers

| # | Story | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|
| 12 | #30–#32 Create case | As `doctor@`: Emergencies → new **critical** case needing 20 O− red cells and 1 ICU bed | Case created with a reference; listed first by priority | | |
| 13 | #33 Local check | Open the case | Shows what CityCare General has and the shortfall per need | | |
| 14 | #37–#42 Matching | On the case: Sources in the network | Other hospitals ranked with distance, ETA and an explanation; compatible blood only | | |
| 15 | #43 #44 Reserve | Reserve what is local | Units held; a second user can't take the same units | | |
| 16 | #47 Transfer request | Request O− from another hospital (e.g. Seaview Hospital) | Transfer requested | | |
| 17 | #52 #53 Alerts (B06, B07) | As `admin@` (acting for the supplier) and as `nurse@` after each move | Notifications for the request and each move; critical ones show a banner until acknowledged; the bell counts unread | | |
| 18 | #47 Approve | As `admin@`: Transfers → Approve | Status Approved; units held at the supplier | | |
| 19 | #51 Dispatch (B05) | As `admin@`: dispatch the transfer with an available ambulance; follow the trip | Transfer Dispatched → In transit; the trip shows the ambulance; the ambulance is busy until the trip ends | | |
| 20 | #49 Receipt | As `bloodbank@`: Transfers → outgoing → Confirm receipt | Delivered; units now at CityCare General and allocated to the case; ambulance available again | | |
| 21 | #45 #46 Allocation | Open the case | Need shows filled units; allocation history listed | | |
| 22 | #34 #35 Status, escalation, closure | Leave a critical case untouched past the escalation time, then close it with an outcome note | Escalated (with a critical alert); close needs a note; closing cancels open transfers | | |
| 23 | #36 Network feed | Emergencies → feed | Other hospitals' open blood requests listed | | |

## Dashboards and oversight

| # | Story | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|
| 24 | #54 Hospital dashboard (B08) | As `doctor@`: Overview; in another tab change a bed; wait a minute | Open emergencies and pending transfers panels; figures refresh without reloading | | |
| 25 | #55 Command centre (B09) | As admin: City command centre | One row per hospital; shortages (e.g. no free ICU bed, low O−) and near-expiry highlighted | | |
| 26 | #56 Audit search/export (B10) | As admin: Audit log → filter by a transfer action → Export CSV | Only matching entries; the CSV has the same rows | | |
| 27 | #72 Public landing | Signed out: / | Live ER status and today's doctors | | |

## Non-functional

| # | Story | Steps | Expected | Pass/Fail | Notes |
|---|---|---|---|---|---|
| 28 | #58 Security | `python manage.py check --deploy` on staging (B13, #108) | No warnings | | |
| 29 | #58 Performance | The search load test from B13 (#108) on staging | p95 recorded for the final report | | |

## Sign-off

- [ ] Accepted by the Product Owner: ________________ on ____________
- Failed rows and their issue numbers: ________________
