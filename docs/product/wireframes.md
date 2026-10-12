# Wireframes (text, low fidelity)

There's no Figma file. These text wireframes are the agreed layout for every staff screen up to Sprint 2.
Visual style comes from `frontend/src/styles/tokens.css` and the specs in `docs/superpowers/specs/`.
Later sprints add their screens here before building them.

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

"–" means the link is hidden. Opening the path directly shows **"You don't have access to this page"** with a
link to Overview, and the API answers 403. A patient opening any `/staff` path sees "This area is for hospital
staff".

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

## Existing Sprint 1 screens

Overview, Beds, Blood bank and Pharmacy are specified in
`docs/superpowers/specs/2026-10-06-staff-workspace-design.md`. Public home, sign in and sign up are in
`docs/superpowers/specs/2026-10-05-landing-and-auth-pages-design.md`.
