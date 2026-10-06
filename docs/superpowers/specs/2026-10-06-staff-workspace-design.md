# Staff workspace: Design

**Status:** Approved by Haris, 6 Oct 2026
**Scope:** frontend only. Shell, Overview dashboard, Beds, Blood bank, Pharmacy. Sample data, in-memory changes.

## Access

> **Changed 7 Oct 2026:** preview mode is gone. The backend (`hassanqureshi/backend`) provides real sign-in, so
> `/staff` asks `GET /api/auth/me/`: signed-out visitors go to `/login?next=…`, patients see "This area is for
> hospital staff", and staff get the workspace with the role from their account. Each page loads only the modules
> the role may see (the API answers 403 otherwise). Bed actions are saved with `POST /api/beds/<id>/actions/`;
> a 409 means someone else moved the bed first, and the board refreshes. The original preview design is kept below.

### Original: preview mode

Login is not wired yet, so `/staff/*` opens in preview mode with a banner:
"Preview: sign-in isn't connected yet. Viewing as [role ▾]". The role decides navigation and actions:

| Role | Overview | Beds | Blood bank | Pharmacy |
|---|---|---|---|---|
| Admin | view | edit | edit | edit |
| Doctor | view | view | view | view |
| Nurse | view | edit | none | view |
| Blood bank | view | none | edit | none |
| Pharmacist | view | none | none | edit |

A page the role can't see shows "You don't have access to this page" with a link to Overview.

## Shell

- Sidebar in `--sign` (the overhead sign), monogram + hospital name, nav items the role can see, active item
  marked with a teal floor-line stripe; user name, role and "Sign out" (→ `/login`) at the bottom.
  Below 960px the sidebar becomes a top bar with a "Menu" disclosure.
- Top bar: page title, current shift with time left (shifts in `hospital.shifts`: Morning 08–14,
  Evening 14–20, Night 20–08), bell with the count of attention items for this role (links to Overview).
- Bed changes made on any page update the Overview and the bell (one shared data store in the layout).

## Overview (`/staff`)

- Four tiles (only modules the role can see; ER tile always): Beds free (n of N, ICU free), ER (waiting,
  approximate wait), Blood (available units, red-cell groups below minimum), Pharmacy (items to reorder,
  medicines expiring within 90 days, matching the Pharmacy filter). Each links to its page; the ER tile links to
  the public page's Emergency section.
- Needs attention: severity-sorted list (critical, then warning), icon + text label, each linking to its page.
  Rules: red-cell group below minimum (critical when below half), available units expiring within 24 h
  (grouped by component), cleaning longer than 45 min, medicine below reorder level (critical when under
  2 days of supply).
- Bed occupancy by ward: stacked horizontal bar per ward (occupied / reserved / cleaning / free, out of
  service excluded), legend, counts as text beside each bar.
- Red-cell stock by group: bar per group with a tick at its minimum, count as text, status badge.
- Expected discharges today: bed, initials, ward.

## Beds (`/staff/beds`)

- Filters: ward, status, "Discharges today". Wards: ICU, HDU, Medical A, Surgical B, Paediatrics, Maternity,
  Isolation. Each ward header: occupancy % and free count.
- Bed tile: label, status (badge), occupied → initials · age · sex, day of stay, expected discharge;
  isolation tag (contact / droplet / airborne); cleaning → elapsed minutes, warning after 45.
- Discharge asks for confirmation ("Discharge S.A. from ICU-03?" → Confirm discharge / Keep patient); every
  status change is announced to screen readers.
- Actions (only roles with edit, only valid transitions):
  occupied → Discharge (→ cleaning, patient cleared) · cleaning → Mark ready (→ free) ·
  free → Reserve (→ reserved) / Take out of service · reserved → Cancel reservation (→ free) ·
  out of service → Return to service (→ cleaning).

## Blood bank (`/staff/blood`)

- Stock grid: 8 groups × 4 components (red cells, plasma, platelets, cryo), available units vs minimum, status
  OK / Low / Critical (Low < minimum, Critical < half of minimum).
- Unit list, first-expiry-first-out: ISBT 128-style unit number, group, component, collected, expires in,
  status (quarantined / available / reserved / issued / expired), storage. Filters: component, status.
- Shelf life (configurable): red cells 42 d at 2–6 °C; platelets 5 d at 20–24 °C agitated; plasma and cryo
  1 year frozen at ≤ −25 °C.
- Compatibility finder (red cells and plasma only): recipient group → compatible donor groups with available
  counts. Red cells: donor ABO antigens ⊆ recipient's, Rh− recipients get Rh− only. Plasma: donor must lack
  antibodies to recipient antigens (AB universal), Rh ignored.
  Note: "Coordination aid: the lab confirms compatibility with a crossmatch."
- Storage and shelf-life panel: per component, shelf life, storage temperature, location and the one handling rule
  that most often goes wrong (e.g. platelets: never refrigerate).
- Sample stock follows Pakistan's blood-group distribution (B+ most common); O− red cells are low.

## Pharmacy (`/staff/pharmacy`)

- Table: generic name, strength and form, category, on hand / reorder level, days of supply
  (on hand ÷ average daily use), nearest expiry, location; tags High-alert (ISMP list: insulin, heparin,
  concentrated KCl, opioids, etc.) and CD (controlled drug, two-person check).
- Filters: All, Below reorder, Expiring ≤ 90 days, High-alert, Controlled; name search.
- Row expands to batches: batch number, expiry, quantity.

## Fonts

Big Shoulders Display (uppercase signage: nav, page titles, tile labels, ward names), Radio Canada (body and
sentence-case card titles), Martian Mono (times, unit numbers, counts).

## Tokens added

`--status-ok #1D7A3E`, `--status-warning #8A5A00` (text); bed fills `--bed-occupied #1C5BB8`,
`--bed-reserved #B03A7E`, `--bed-cleaning #C2850C`, `--bed-free #2B8A4E` (validated with the dataviz
palette checker: lightness, chroma, CVD and contrast all pass).

## Built during implementation

- Links to `#attention` / `#emergency` scroll to their section after in-app navigation (`useScrollToHash`).
- Shared `FilterBar`, `Panel`, `StatusBadge`, `.table-scroll`, and date helpers in `lib/time`.

## Out of scope

Real auth, persistence, patients/charts/orders, emergency requests, transfers, stock receive/dispense.
