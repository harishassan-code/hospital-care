# Wireframes (text, low fidelity)

There's no Figma file. These text wireframes are the agreed layout for every staff screen up to Sprint 2, plus
low-fidelity drafts of the core journeys still to come (emergency request, matching results, transfer tracking)
for refinement before those sprints. Visual style comes from `frontend/src/styles/tokens.css` (light and dark,
following the system setting) and the specs in `docs/superpowers/specs/`.

## Navigation map

The staff workspace (`/staff`) has a sidebar (top bar with a **Menu** button on narrow screens). It lists only the
modules the signed-in role can open (`ACCESS` in [api-contracts.md](../architecture/api-contracts.md)).

| Screen | Path | admin | doctor | nurse | bloodBank | pharmacist | patient |
|---|---|---|---|---|---|---|---|
| Public home | `/` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Sign in / sign up | `/login`, `/signup` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Overview | `/staff` | ✓ | ✓ | ✓ | ✓ | ✓ | – |
| Beds | `/staff/beds` | edit | view | edit | – | – | – |
| Blood bank | `/staff/blood` | edit | view | – | edit | – | – |
| Pharmacy | `/staff/pharmacy` | edit | view | view | – | edit | – |
| Hospitals list | `/staff/hospitals` | edit | view | view | view | view | – |
| Hospital detail | `/staff/hospitals/:id` | edit | view | view | view | view | – |
| Register / edit hospital | `/staff/hospitals/new`, `/:id/edit` | ✓ | – | – | – | – | – |
| Users and roles | `/staff/users` | ✓ | – | – | – | – | – |
| Planned modules (placeholder) | `/staff/emergencies`, `/matching`, `/transfers`, … | ✓ | ✓ | ✓ | ✓ | ✓ | – |

"–" means the link is hidden. Opening the path directly shows **"You don't have access to this page"** with a
link to Overview, and the API answers 403. A patient opening any `/staff` path sees "This area is for hospital
staff".

### Proposal roles and app roles

The proposal (§6) names five roles. The app has six (`accounts.Role`). Until #9 settles it, they map like this:

| Proposal role | App role today | Sees |
|---|---|---|
| System Administrator | `admin` | Everything, including Users and roles |
| Hospital/Blood-Bank Staff | `nurse`, `bloodBank`, `pharmacist`, `doctor` | Their module(s), their own hospital |
| Emergency/Clinical Coordinator | `doctor` for now. **A `coordinator` role is an open decision (#9).** | Will need Emergency requests and Matching (Sprints 5–6) |
| Hospital Management | **No role yet (open decision, #9)**. A view-only `management` role would see Overview and reports. | Overview; reports (#66) |
| Participating Hospitals | Each hospital's own staff accounts | Their hospital's resources |

## States every staff screen has

- **Loading:** "Loading…" in a `role="status"` line.
- **Failed:** "The hospital's system didn't respond…" plus the hospital's phone number.
- **No access:** the panel described above.
- **Empty:** a sentence saying what's missing and, for editors, how to add the first one.

## Hospitals list (`/staff/hospitals`)

```
┌ HOSPITALS ───────────────────────────────────────── [Register a hospital] (admin only)
│ Search hospitals [______________]   Show: [All 3] [Hospitals 2] [Blood banks 1]
│ ┌──────────────────────────┬────────────┬───────────────────────┬───────────────┐
│ │ Name (link to detail)    │ Type       │ Address               │ Status        │
│ │ CityCare General Hospital│ Hospital   │ Shahrah-e-Faisal, …   │ ✓ Active      │
│ │ Old Town Blood Centre    │ Blood bank │ …                     │ ● Deactivated │
│ └──────────────────────────┴────────────┴───────────────────────┴───────────────┘
```
States: loading, failed, empty ("No hospitals registered yet."), no matches ("No hospitals match …").

## Hospital detail (`/staff/hospitals/:id`)

```
┌ ← All hospitals
│ CITYCARE GENERAL HOSPITAL   Hospital · ✓ Active            [Edit details] (admin)
│ Address, phone, coordinates (lat, lng)
├ Capabilities: [Trauma centre] [ICU] [Blood bank] …   or "No capabilities recorded."
├ Departments ─ list ─ [Remove] (admin)  + "Department name [____] [Add department]" (admin)
├ Wards ─ name · kind · department · N beds ─ [Remove] (admin, refused while beds exist)
│        + "Ward name [__] Kind of care [__] Department [select] [Add ward]" (admin)
└ Storage locations ─ list ─ [Remove] (admin)  + "Location name [__] [Add location]" (admin)
```
States: loading, failed, not found ("No hospital with that id."). Each add form validates and announces its own
errors. A refused removal shows the server's reason in a `role="alert"` line.

## Register / edit hospital (`/staff/hospitals/new`, `/staff/hospitals/:id/edit`; admin)

```
┌ REGISTER A HOSPITAL / EDIT <NAME>
│ Name*            [______________________]
│ Type*            (•) Hospital  ( ) Blood bank
│ Address*         [______________________]
│ Latitude*  [_______]   Longitude* [_______]   hint: decimal degrees, e.g. 24.8607
│ Phone (optional) [__________]
│ Capabilities     [x] Trauma centre [ ] NICU …  (fieldset with legend)
│ [x] Active: accepting requests from the network   (edit only)
│ [Save hospital]   Cancel
```
Errors appear under each field. Focus moves to the first invalid field, and server errors show in a
`role="alert"` box. On success the browser opens the hospital's detail page.

## Users and roles (`/staff/users`; admin)

```
┌ USERS AND ROLES
│ ┌──────────────┬──────────────────────┬──────────────┬───────────────┬──────────┐
│ │ Name         │ Email                │ Hospital     │ Role          │          │
│ │ Hina Javed   │ nurse@demo…          │ CityCare Gen │ [Nurse     ▾] │ [Save]   │
│ │ Amna Admin   │ admin@demo…          │ CityCare Gen │ Admin (you)   │          │
│ └──────────────┴──────────────────────┴──────────────┴───────────────┴──────────┘
│ status line (aria-live): "Hina Javed is now a Doctor. The change applies on their next page load."
```
Locked rows (your own account, superusers) show the role as text with the reason. States: loading, failed, and a
failed save (message in `role="alert"`, select reverts).

## Beds additions (Sprint 2: #23, #25)

The bed board gets a line above the wards: "Occupancy by bed type: ICU 89% · 0 free of 18, General 71% · …".
Each ward header shows "⚠ At or above 90%" when its occupancy reaches `occupancyAlertPercent` in
`src/config/hospital.ts`. The overview's occupancy chart flags the same wards.

## Planned journeys (drafts for refinement)

### Emergency request: create and track (`/staff/emergencies`, Sprint 5)

```
┌ NEW EMERGENCY REQUEST
│ Severity*        (•) Critical  ( ) Urgent  ( ) Routine
│ Needed*          [Blood ▾]  Group* [O- ▾]  Component* [Red cells ▾]  Quantity* [4]
│                  + Add another requirement (bed, equipment…)
│ Patient ref      [__________] (optional, no names)
│ [Submit request]
└───────────────────────────────────────────────────────────
┌ REQUEST #2026-0142 · CRITICAL · ● Partially fulfilled (2 of 4 units)
│ Timeline: 14:02 Open → 14:02 Matching → 14:09 Partially fulfilled (reserved 2 at Seaview)
│ [Find more]  [Escalate]  [Close…] (asks for an outcome note)
```
States: validation errors on the fields, and an escalation banner (role="alert") when the timer fires.

### Matching results (Sprint 6)

```
┌ CANDIDATES FOR O- RED CELLS × 4                         sorted by: score ▾
│ #1 Seaview Hospital  · 3 units · 6.2 km · ~14 min · expiring soonest first   [Reserve 3]
│     Why: compatible (O- for O-), 3 tested units, nearest with stock
│ #2 Northside Children's · 1 unit · 9.8 km · ~22 min                           [Reserve 1]
│ Deactivated hospitals and units already reserved are never listed.
```
States: no matches ("No compatible units in the network. Escalate?"), loading, a reservation conflict
("Someone reserved these first; the list is refreshed").

### Transfer tracking (Sprint 7)

```
┌ TRANSFER T-0031 · Seaview Hospital → CityCare General · 3 × O- red cells
│ ✓ Requested 14:10 · ✓ Approved 14:12 (Tariq L.) · ● Dispatched 14:20 · ○ In transit · ○ Delivered
│ Supplier: [Approve] [Reject…] (reason required)    Receiver: [Confirm delivery]
```
States: rejected (shows the reason), cancelled, delivered (inventory updated on both sides).

## Existing Sprint 1 screens

Overview, Beds, Blood bank and Pharmacy are specified in
`docs/superpowers/specs/2026-10-06-staff-workspace-design.md`. Public home, sign in and sign up are in
`docs/superpowers/specs/2026-10-05-landing-and-auth-pages-design.md`.
