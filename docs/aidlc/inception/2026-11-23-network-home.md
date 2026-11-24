# Inception Spec: CityCare network home and public hospital pages

**Date:** 2026-11-23
**Author:** Haris Hassan (Claude, drafted for review)
**Bolt:** [B19](../bolts/B19-network-home.md)
**Related backlog item:** the account owner's request of 23 Nov (a GitHub issue is opened when this is approved)

## Problem

The public home page was designed in October for a single hospital: "Where do you need to go?", one emergency
department's status and wait (`EmergencyStatus`, a single row for the whole system) and one doctor rota
(`DoctorShift`, which has no hospital at all). CityCare is a network that any hospital can join, so the page
misleads: a visitor can't tell which hospital the wait belongs to, and a patient who signs in lands on one hospital's
timetable. Each hospital's doctors, departments and resources belong on that hospital's own page.

For: members of the public and patients (choosing where to go), hospitals considering joining and the Product Owner
(what the service is), staff (signing in).

## User stories

- As a member of the public or a patient, I want to see the network's hospitals with each one's emergency status and
  waiting time, so that I can choose where to go.
- As a patient, I want each hospital's own page with its services, departments and who is on duty, so that I see a
  hospital's details when I choose it, not before.
- As a hospital considering joining, I want the home page to explain what CityCare does for patients, hospitals and
  staff, so that I understand the service.
- As staff, I want to sign in from the home page, as today.

## Acceptance criteria

**Home page** (`/`, no sign-in):
- [ ] A hero that presents the network: one line on what CityCare is (hospitals sharing beds, blood, equipment,
      operating rooms and ambulances so emergencies get what they need), with the city network illustration.
- [ ] A live city snapshot from the API: hospitals in the network; emergency departments accepting / very busy /
      not accepting ambulances; the shortest current wait and where; bed availability across the network by type as
      a level (Available / Limited / Full); blood supply per group as a level (OK / Low / Critical); ambulances
      available. With the time it was updated.
- [ ] A hospital directory: one card per active member hospital with name, area, kind (hospital, blood bank), key
      services, emergency status and wait, linking to its page. Sorted by shortest wait, or by distance when the
      visitor chooses "Use my location" (see Q2).
- [ ] "How CityCare works", three short columns: for patients, for hospitals, for staff.
- [ ] Sign-in options for patients and staff (as today), and the emergency number (1122) on every public page.
- [ ] No doctor rota or department timetable on the home page.

**Hospital page** (`/hospitals/:id`, no sign-in):
- [ ] Emergency status, estimated wait, people waiting and when it was updated.
- [ ] Services (capabilities) and departments.
- [ ] On duty now, by department: specialties and how many doctors; names only for signed-in hospital staff (F5,
      unchanged).
- [ ] Bed availability by type, as levels (Q1).
- [ ] Address with a map link, phone, and a link back to the network.
- [ ] An unknown or inactive hospital shows a "not found" page, not an error.

**After sign-in:** patients land on the home page as today. Staff land in the workspace as today.

**Per-hospital emergency status:**
- [ ] `EmergencyStatus` belongs to a hospital (one per hospital). The migration gives the existing row to the first
      hospital, and hospitals without one show "status not reported".
- [ ] Staff with the Emergencies module (admin, doctor, nurse) can update their own hospital's status, wait and
      number waiting from the staff Emergencies page; it's audit-logged (`er_status.update`). B21 updates it
      automatically on staging.
- [ ] `DoctorShift` and the old `GET /api/public/status/` are removed; "on duty" comes from the per-hospital
      specialists and their on-call windows (B16), and from the staff rosters once B20 adds them.

**Quality:**
- [ ] Public endpoints return statuses, levels and counts only: no patient data, and no doctor names for anonymous
      callers (tests for both).
- [ ] Tests: backend endpoint tests (levels, inactive hospitals hidden, names hidden when anonymous, status update
      permissions and audit); frontend tests for both pages; QA tests updated with `arrayContaining`; the e2e scenario
      stays green.
- [ ] Works on a phone, in light and dark mode, with keyboard and screen reader (landmarks, headings, labels).

## Design

- **Backend** (`apps/emergencies` for the public views, `apps/hospitals` for the data):
  - `EmergencyStatus.hospital` (one-to-one, `PROTECT`) with a data migration; `apps/emergencies/services.py` gains
    `update_status(actor, hospital, ...)` (audit-logged) and `network_snapshot()`.
  - `GET /api/public/network/`: the snapshot. `GET /api/public/hospitals/`: the directory. `GET
    /api/public/hospitals/<id>/`: one hospital. All `AllowAny` with session authentication (names for staff only),
    like `PublicStatusView` today. `PUT /api/hospitals/<id>/emergency-status/`: staff update, with the
    `emergencies` module permission and own-hospital scoping.
  - Levels are computed on the server, so the public never receives exact stock: beds by type are *Available* when
    at least 15% are free, *Limited* when at least one is free, otherwise *Full*; blood per group is *OK* above
    `BLOOD_LOW_STOCK_UNITS`, *Low* at or below it, *Critical* at zero.
  - Remove `DoctorShift` (model, admin, seed) and `PublicStatusView` with their tests; migrations committed.
- **Frontend:**
  - `pages/LandingPage.tsx` rewritten from `features/network/` components: `NetworkSnapshot`, `HospitalDirectory`,
    `HowItWorks`; `SignInOptions` and `CityNetwork` reused. `pages/HospitalPublicPage.tsx` for `/hospitals/:id`.
  - `api/public.ts` replaces `api/publicStatus.ts`; mocks in `src/test/mockApi.ts`.
  - Removed: `DoctorSchedule`, `WayfindingSign`, `EmergencyStatus` (landing), `schedule.ts` and their tests.
  - Staff Emergencies page: a small "Our emergency department" form for the status update.
- **Docs:** `api-contracts.md`, `api.md`, `user-manual.md` (public pages), `design-system.md` if a pattern is added.

## Non-goals

- Patient accounts with records, appointments or messages.
- A map with tiles (the directory and the illustration are enough; a map provider needs a key and a privacy review).
- Changing what the staff workspace shows (B22).

## Open questions

Proposed answers; the account owner confirms them at sign-off:

1. **Exact bed counts for the public, or levels?** *Proposed:* levels (Available / Limited / Full) per bed type, and
   blood levels per group. Exact stock is operational information a hospital may not want public, and a level is
   enough to choose where to go. Staff keep the exact numbers in the workspace.
2. **Sort by distance?** *Proposed:* yes, only after the visitor presses "Use my location". The browser works out the
   distances; the location is never sent to the server or stored.
3. **Doctor names on the public hospital page?** *Proposed:* no, as decided for F5 (B13): the public sees specialties
   on duty and counts; signed-in hospital staff see names.
4. **Who updates a hospital's emergency status?** *Proposed:* staff at that hospital with the Emergencies module
   (admin, doctor, nurse), from the staff Emergencies page; on staging the simulation (B21) keeps it current.
5. **Patients after sign-in?** *Proposed:* the same network home page (no patient records exist to show).

## Approval

- [x] Approved by: Haris Hassan (`harishassan-code`, account owner) on 2026-11-23, all proposed answers accepted
