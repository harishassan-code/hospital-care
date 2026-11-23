# Inception Spec: Every page with a purpose, an action and charts

**Date:** 2026-11-23
**Author:** Haris Hassan (Claude, drafted for review)
**Bolt:** [B22](../bolts/B22-purposeful-pages.md)
**Related backlog item:** the account owner's request of 23 Nov (a GitHub issue is opened when this is approved)

## Problem

Most staff pages show current numbers and lists. They don't say what needs doing, and they can't show whether
things are getting better or worse, because there are no trends. With live data (B21) and history (B20) the pages can
answer the questions staff actually ask, point to the next action, and show trends as charts. The live data also
needs two pages it doesn't have yet: the emergency department queue and who is on duty.

For: every staff role, the Product Owner (does each page earn its place?), demo audiences.

## User stories

- As any staff member, I want each page to tell me what needs my attention and let me act on it there, so that I
  don't have to read a table to find out.
- As a manager, I want trends as charts (today against a typical day, the last week), so that I can see whether
  things are getting better or worse.
- As emergency staff, I want a live queue by triage level with waiting times and the factors behind the estimate, so
  that I can see who is next and why the wait is what it is.
- As a manager, I want to see who is on duty against the plan, so that I can cover gaps.

## Acceptance criteria

**The purpose of each page.** Each page states its question in its header line, leads with what needs action, and
gets the charts below. `docs/product/page-purposes.md` records this table and is checked page by page at review.

| Page | The question it answers | Main actions | Charts |
|---|---|---|---|
| Overview | What needs me now, at my hospital? | Each attention item links to where it's fixed | Arrivals and discharges per hour today against the 14-day typical day; occupancy over 7 days |
| **Emergency department** (new) | Who is waiting, who is next, and why is the wait what it is? | Start treatment, admit, discharge, transfer; update the department's status | Arrivals per hour today against typical; estimated wait over 24 hours; the queue by triage level |
| Emergency cases | Which cases still lack something, and since when? | Open a case, match, escalate | Open cases by severity over 7 days |
| Beds | Where can the next patient go, and which beds are about to free up? | Admit, discharge, mark cleaned | Occupancy by bed type over 7 days; beds freeing up in the next 12 hours |
| Blood | Which groups run short, and what expires first? | Reserve, issue, discard expired, book donors | Stock by group against the low-stock line; issued against donated over 14 days |
| Donors | Who can donate now, and who is booked? | Book, record a donation | Donations per day over 14 days |
| Operating rooms | Which rooms are free now and later today, and is the list running late? | Start, finish, clean, book, cancel | Today's timeline per room; use over 7 days; cancellations |
| **Staff on duty** (new) | Who is on duty now, who is missing, and is any ward short? | Mark late or absent, see a person's shifts | Staff on duty through the day against plan; nurse-to-patient ratio by ward |
| Equipment | Which devices are free, and which are out of service? | Reserve, release, send to maintenance | Ventilators and monitors in use over 24 hours |
| Ambulances | Which vehicles are free, and which trips are late? | Dispatch, update a trip | Trips per hour; average trip time over 7 days |
| Pharmacy | What runs out first? | Reorder note, check batches | Days of stock for the medicines nearest their reorder level |
| Transfers | What is on its way to us, and from us? | Approve, dispatch, confirm delivery | Transfers per day over 14 days |
| Command centre | Which hospitals are under strain, and what is moving between them? | Open a hospital, a case or a transfer | Hospitals ranked by strain; a small chart per hospital of occupancy over 24 hours; emergency waits side by side |
| Reports | What happened over a period? | Export CSV or PDF | The report's figures as charts on screen |
| Alerts, Audit, Hospitals, Specialists, Users | (lists and admin) | as today | none: their purpose is a list or a form |

**Charts:**
- [ ] A small in-house chart kit in `components/charts/`: line or area over time (with a "typical day" band), bars
      with a threshold line, stacked bars, a timeline, and sparklines. SVG, design tokens only, light and dark, a
      tooltip on hover and keyboard focus, and a "Show as table" alternative for screen readers. The palette is
      checked with the data-visualisation validator, and status colours always come with a word, never colour alone.
- [ ] `GET /api/metrics/?metric=&from=&to=&bucket=hour|day` (own hospital; network-wide for admins and the command
      centre), from B20's snapshots. Each chart says what it shows and when it was updated.

**New pages:**
- [ ] **Emergency department** (`/staff/emergency-department`): the queue from B21's `ErVisit` (tags, age band, triage
      level, waiting time, never names), the wait estimate with its factors, and the actions above, through the
      services, audit-logged.
- [ ] **Staff on duty** (`/staff/staffing`): from B20's rosters and B21's clock-ins.
- [ ] Both in `roles.ts` and `permissions.py` together (emergency department: admin, doctor, nurse; staffing: admin,
      doctor, nurse), with `api-contracts.md` updated.

**Quality:**
- [ ] Tests per chart component (renders, tooltip, table alternative), per new endpoint and role, per new page; QA
      tests use `arrayContaining`; the e2e scenario stays green.
- [ ] No page waits on its charts: the main content and actions load first, then the charts.

## Design

- `components/charts/` (`TimeSeriesChart`, `ThresholdBars`, `StackedBars`, `Timeline`, `Sparkline`, `ChartFrame` with
  the title, the table toggle and the updated time), built on the existing hand-drawn `OccupancyChart` and
  `RedCellChart`, which move into the kit.
- `apps/metrics`: the read endpoint with own-hospital scoping (`own_hospital`), `module_permission("metrics")`.
- Pages change one at a time, in the order in Q2; each is a small unit in the construction plan.

## Non-goals

- A configurable dashboard builder.
- New modules beyond the two pages above.

## Open questions

Proposed answers; the account owner confirms them at sign-off:

1. **A chart library, or our own?** *Proposed:* our own small kit. No new dependency (the main bundle is already
   about 520 kB), charts that match the design system exactly in both themes, and accessibility (focus, tooltips,
   table view) under our control. The two charts already in the app show the approach works.
2. **Which pages first if time runs short?** *Proposed:* Overview, Emergency department, Blood, Beds, Command centre;
   then Operating rooms and Staff on duty; then the rest.
3. **The two new pages?** *Proposed:* yes. They are where the live data from B21 is acted on; without them the
   simulation would only be visible as numbers changing.

## Approval

- [ ] Approved by: <name> on <date>
