# Inception Spec: City command centre dashboard

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B09](../bolts/B09-city-command-centre.md)
**Related backlog item:** [#55 City command centre dashboard](https://github.com/harishassan-code/hospital-care/issues/55)
(Epic E7, Sprint 8, listed in the [product backlog](../../product/backlog.md); builds on #38
[find candidate hospitals](2026-11-17-find-candidate-hospitals.md), #43
[atomic resource reservation](2026-11-17-atomic-resource-reservation.md) and #45
[allocation](2026-11-17-allocation-record-and-blood-allocation.md). The refresh is separate from the
[hospital dashboard](../bolts/B08-hospital-dashboard.md).)

## Problem

Nobody sees the whole network on one page. Overview shows the figures for the user's own hospital. An admin
without a hospital sees network totals, with no split by hospital. The network feed (#36) lists active emergency
requests from every hospital, but it shows no stock, beds or rooms. To find which hospital is short of blood, or
which hospital has units about to expire, someone has to open each hospital's pages.

This is for hospital management, who monitor conditions across the city. There is no management role yet (the
wireframes leave it open as decision #9). In the MVP, only the admin role sees the page.

## User stories

- As management, I want one page with availability, shortages and active emergencies for every hospital, so that
  I can monitor conditions across the city. (#55)
- As management, I want the shortages and near-expiry stock listed first and in words, so that I can see where to
  act without comparing numbers.
- As management, I want the figures to refresh on their own, so that the page is current while I watch it.

## Acceptance criteria

### Data

- [ ] One endpoint, `GET /api/command-centre/`, returns every figure on the page. The page makes no other read for
      its figures.
- [ ] It covers every active hospital. Each hospital has one row with:
  - [ ] red cells available for each of the eight blood groups, with the minimum and the level (see the rules below);
  - [ ] usable blood units of all four components, and how many of them are near expiry;
  - [ ] free beds by bed type (five types), available equipment by type (four types), and available operating rooms;
  - [ ] active cases: how many, and how many of them are escalated;
  - [ ] open needs by resource type: quantity less fulfilled less held, summed over the hospital's active cases.
- [ ] Network totals are the sum of the hospital rows. The response also gives `updatedAt` and the near-expiry window
      in days, so the page can say what "near expiry" means.

### Shortages and expiry

- [ ] A red-cell group at a hospital is **Low** below its minimum and **Critical** below half of it. The level is
      written in words with the count and the minimum, for example "Critical: 1 unit, minimum 4".
- [ ] A summary above the table lists, in words, each blood group that is short at one or more hospitals, with how
      many hospitals are critical and how many are low.
- [ ] Hospitals with a critical shortage are listed first, then the rest by name.
- [ ] Near-expiry units are shown as a count in words at each hospital ("2 expire within 3 days"), and as a network
      total.
- [ ] No status depends on colour alone. Every shortage and near-expiry figure has words beside it. Colour may be
      added on top.
- [ ] A hospital with no shortage and no near-expiry units says "No shortages" in words.

### Who can see it

- [ ] A module `commandCentre` is added to `ACCESS` in `backend/apps/accounts/permissions.py` and to `roles.ts`. Only
      the admin role has a row, with view. Both tables change together, and `docs/architecture/api-contracts.md`
      gets the matching row.
- [ ] Other roles and patients get 403 from the endpoint, and the menu does not show the link to them.
- [ ] The page is read-only. It has no button that changes stock, beds, rooms, equipment or cases.

### Refresh

- [ ] The page loads the figures again every 60 seconds while it is open.
- [ ] The page shows when the figures were last updated, from `updatedAt`.
- [ ] If a refresh fails, the last figures stay on the page, with a `role="alert"` line saying they may be out of
      date. The page does not go blank.
- [ ] No websockets and no server push.

### Query budget and speed

- [ ] On the seeded demo network, the endpoint answers in under one second.
- [ ] The number of queries is fixed: at most 15 for the service call on the seeded demo network, not counting
      sign-in. A test adds two active hospitals with stock and cases, and checks that the count does not change.
- [ ] The request-time sweeps (`escalate_overdue` and `release_expired`) run first, so held stock and escalated
      cases match the case pages.
- [ ] A test checks that the red-cell counts for a seeded hospital equal the counts in the Blood page's stock
      summary for the same hospital.

### Privacy and the page

- [ ] The response holds counts, hospital names and hospital ids only. It has no patient fields, no case references,
      no staff names and no unit or asset identifiers.
- [ ] The page lives at `/staff/command-centre` and replaces the placeholder. `commandCentre` is added to `MODULES`
      and the path is removed from `planned.ts`.
- [ ] The endpoint is mocked in `frontend/src/test/mockApi.ts`, so the page's tests run against the real shape.

## The rules in one place

| Thing | Rule |
|---|---|
| Who sees it | Admin only, view (`commandCentre`). No new role. See question 1. |
| Hospitals counted | Active hospitals only. Matching leaves inactive hospitals out too. |
| Red-cell minimum | `MINIMUM_STOCK.redCells` on Overview (`frontend/src/api/blood.ts`). The backend keeps a copy, with a comment pointing to it. |
| Shortage level | `ok` at or above the minimum, `low` below it, `critical` below half of it. The same rule as `stockLevel` in `blood.ts`. Judged per hospital, for red cells only. |
| Usable stock | Units that are `available` and not past expiry (`usable_units`). Reserved, quarantined and issued units don't count as free. |
| Near expiry | Usable units expiring within `BLOOD_NEAR_EXPIRY_DAYS` (3 by default). |
| Free or available | Beds `free`, equipment `available`, operating rooms `available`. Held items are not free. |
| Active case | `open`, `matching`, `partiallyFulfilled` or `escalated`. The same set as the network feed. |
| Open need | `quantity − fulfilled − held` for each need of an active case, as in #45. |
| Totals | Sums over the active hospitals. A level is never worked out from a total. |
| Refresh | Every 60 seconds, from the page. |
| Privacy | Counts, hospital names and ids. Nothing that identifies a patient, a case or a unit. |

## Non-goals

- A map or any geographic view. Distances are not shown on this page.
- Live push (websockets or server-sent events). The page reloads its figures on a timer.
- History, trends or charts over time. That is stretch item [B18](../bolts/B18-reports.md).
- Export, print or PDF. Also B18 (#66, #67).
- Changing anything from the page: stock, beds, rooms, equipment or cases.
- Case lists and patient-level detail. The network feed on Emergencies stays where it is.
- Per-case shortfall or "who can cover what". That is the case page's Sources panel (#38).
- Pharmacy stock, ambulances and the progress of transfers (B02, B04, B05).
- Notifications and alerts (B06, B07).
- A `management` role (#9).
- Changes to Overview, or to the refresh in `StaffProvider` (B08 decides that).
- Minimums that differ from hospital to hospital.
- Donors and donation appointments.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Who is "management"?** Proposed: admin only, with view on `commandCentre`. No new role.
   Reason: there is no management role yet, and the wireframes leave it open (#9). A new role would change the role
   list, the Users page and the access table, which is more than this bolt. The admin can see the page now, and a
   view row can be added for a role once #9 decides.
2. **Which window counts as near expiry?** Overview's attention list uses 24 hours, and the Blood page's stock uses
   `BLOOD_NEAR_EXPIRY_DAYS`, which is 3 days by default. Proposed: the 3-day window. Reason: a 24-hour window
   shows too few units to show a network shortage. The 24-hour list stays on Overview for each hospital to act on.
3. **Which stock counts for a shortage?** `MINIMUM_STOCK` has minimums for all four components, but Overview judges
   only red cells. Proposed: red cells only. Reason: this matches Overview. The other components show counts here
   but no shortage level. Widening this is a product decision for the Product Owner.
4. **Are inactive hospitals listed?** Proposed: no. Reason: matching leaves them out, so their stock is not part of
   the network. The admin can still see them on the Hospitals page.
5. **How often does the page refresh?** Proposed: every 60 seconds, from the page itself. Reason: each read runs the
   request-time sweeps, so a faster timer adds writes for little gain on a monitoring page. B08 may move the
   polling into `StaffProvider` later; that is its decision.
6. **Where does the minimum table live?** Proposed: a copy of `MINIMUM_STOCK.redCells` in the backend
   (`apps/blood/services.py`), with a comment pointing to `blood.ts`. The response carries each group's minimum and
   level, so the page does not work them out itself. Reason: the server must judge the levels, so the totals and the
   tests agree. Ceiling: two copies. If they drift, move the table into one JSON file that both sides read.
7. **Should this request run the sweeps?** Proposed: yes. `escalate_overdue()` and `release_expired()` run first, as
   the feed and the case pages do. Reason: a hold that has run out stays `held` until a sweep runs, so without it the
   counts would differ from the case pages. Ceiling: a GET that writes, the same as the existing reads (#43).
8. **Does the page list the near-expiry units?** Proposed: counts only, with no unit numbers. Reason: management
   needs the numbers. The unit list stays on each hospital's Blood page, and this keeps identifiers off the
   management page.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
