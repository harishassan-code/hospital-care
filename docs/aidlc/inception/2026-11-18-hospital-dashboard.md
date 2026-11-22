# Inception Spec: Hospital dashboard: open requests, transfers and live refresh

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B08](../bolts/B08-hospital-dashboard.md)
**Related backlog item:** [#54 Hospital dashboard](https://github.com/harishassan-code/hospital-care/issues/54) (Sprint 8;
builds on the Overview page that already shows beds, blood and pharmacy, [#47 transfer request](2026-11-18-transfer-request.md)
(B01) and [#48 transfer tracking](2026-11-18-transfer-tracking.md) (B02))

## Problem

The Overview page shows four status tiles (beds, Emergency, blood, pharmacy), the needs-attention list and two charts. It
does not show the hospital's open emergency requests or the transfers that are waiting. Staff open the Emergencies and
Transfers pages to find out. The page also shows the data from the moment it opened. Nothing changes until someone reloads.

This is for hospital staff who start their shift on the Overview: the emergency coordinator (doctor or nurse), the blood
bank that answers transfer requests, and admins who see the whole network.

This bolt needs B01's `transfers` module and list API. The Transfers link goes to the page that B02 delivers.

## User stories

- As hospital staff, I want a dashboard of my open requests and pending transfers, so that I see my situation at a glance. (#54)
- As hospital staff, I want the Overview to update on its own, so that I don't reload the page to see a change. (#54)

## Acceptance criteria

### Open requests tile

- [ ] The Overview has an **Open requests** tile, placed after the Emergency tile. Its value is the number of open cases at
      the user's hospital. Users without a hospital (admins) count the whole network, as the case list does today.
- [ ] A case is open when its status is **open**, **matching**, **partially fulfilled** or **escalated**. Fulfilled, closed
      and cancelled cases are not counted.
- [ ] The tile's badge is critical ("N critical") when at least one open case has severity critical. Otherwise it is ok
      ("None critical").
- [ ] The tile links to `/staff/emergencies`.
- [ ] The data comes from `GET /api/emergencies/`, which already exists. The page keeps the four open statuses. No new endpoint.

### Transfers tile

- [ ] The Overview has a **Transfers** tile, placed after the Open requests tile. Its value is the number of pending transfers
      at the user's hospital, in both directions. Users without a hospital (admins) count the whole network.
- [ ] A transfer is pending when its status is **requested**, **approved**, **dispatched** or **in transit**. Delivered,
      rejected and cancelled transfers are not counted.
- [ ] The tile's detail reads "N to answer · M outgoing". "To answer" is incoming transfers with status requested. "Outgoing"
      is pending transfers the hospital asked for.
- [ ] The badge is warning ("N waiting for an answer") when "to answer" is above 0. Otherwise it is ok ("Nothing to answer").
- [ ] The tile links to `/staff/transfers`.
- [ ] The data comes from `GET /api/transfers/?direction=incoming` and `GET /api/transfers/?direction=outgoing` (the B01 list
      API). The page keeps the pending statuses.
- [ ] If the transfers request fails, the tile shows "Unavailable" with a neutral badge ("Check the Transfers page"). The
      other tiles still show. This is the same rule as the Emergency tile.

### Permissions by role

- [ ] Open requests tile: all five roles (every role can view Emergencies).
- [ ] Transfers tile: admin, doctor, nurse and blood bank. The pharmacist doesn't see it.
- [ ] Everyone who sees the Transfers tile sees the same count. The tile doesn't say who can answer.
- [ ] The dashboard has no buttons that change anything. Answers happen on the Transfers page (B01, B02).

### Live refresh

- [ ] The staff workspace (`StaffProvider`) reloads its data every 30 seconds. It makes the same calls as the first load for
      the user's role.
- [ ] A tick is skipped while the browser tab is hidden. When the tab is shown again, the data reloads once.
- [ ] A tick is skipped while the previous reload is still running. Two reloads never overlap.
- [ ] A reload does not show "Loading…" again, and does not close open forms or dialogs.
- [ ] The Overview shows "Updated HH:MM", the time of the last successful reload.
- [ ] If a reload fails, the data on screen stays. The Overview line says "Couldn't update. Showing data from HH:MM." The next
      tick tries again.
- [ ] If the first load fails, the page shows today's message (`StaffDataState`).

### Unchanged

- [ ] The beds, Emergency, blood and pharmacy tiles, the Needs attention list, the occupancy chart, the red-cell chart and
      Expected discharges keep their current behaviour.

### Tests

- [ ] The open, critical, pending and "to answer" rules are in one pure function with unit tests. The tests cover the
      unavailable transfers case.
- [ ] `OverviewPage` tests cover the tiles for each role (admin, doctor, nurse, blood bank, pharmacist), the unavailable
      state, and the tile list test is updated for the new tiles.
- [ ] Refresh tests use fake timers. They check: a reload after 30 seconds, no reload while hidden, no overlap, and a failed
      reload that keeps the data and shows the line.
- [ ] `frontend/src/test/mockApi.ts` mocks the transfers list for both directions, in the shape B01 returns.
- [ ] No new endpoint, so no new backend tests.

## The rules in one place

| Thing | Rule |
|---|---|
| Open case | Status open, matching, partially fulfilled or escalated. This is the same set as the network feed (`FEED_STATUSES` in `backend/apps/emergencies/views.py`). |
| Critical request | An open case with severity critical. |
| Pending transfer | Status requested, approved, dispatched or in transit. |
| To answer | An incoming transfer with status requested. |
| Scope | The user's hospital (`own_hospital`). Users without a hospital see the whole network. |
| Who sees the tiles | Open requests: all roles. Transfers: admin, doctor, nurse and blood bank (the module view from B01). |
| Refresh | Every 30 seconds. It reloads the `StaffProvider` data only. Paused while the tab is hidden. Never two at once. |
| Failure | Keep the data on screen and show the last successful time. A section that fails on the first load shows "Unavailable". |
| Server side effects | `GET /api/emergencies/` runs the escalation sweep, as it does today. Each reload runs it again. Fine at MVP scale. |
| Local changes | A bed or blood change saved while a reload is running can be replaced by that reload's older answer. The next reload corrects it. |

## Non-goals

- Push updates (WebSocket or server-sent events). Polling only.
- Refreshing pages that load their own data: the case list, the case page, the network feed, Reserved for cases, users and
  hospitals. They load once when opened, as they do today.
- Attention items for requests or transfers. The Needs attention list stays as it is.
- Answering, dispatching or cancelling transfers from the dashboard. Those are on the Transfers page (B01, B02).
- Held reservations on the dashboard. The case page and the Blood page already show them.
- Paging, or a status filter on `GET /api/emergencies/`. Add it when the list grows.
- The city-wide view (B09) and notifications (B06, B07).

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Points re-estimated from 5 to 3 because most of the story already shipped. Confirm at planning.** Proposed: keep 3 points.
   Reason: the beds, blood and pharmacy tiles and both charts already ship on Overview. What is left is two tiles, one
   refresh loop and tests.
2. **Which open cases count?** Proposed: open, matching, partially fulfilled and escalated. Reason: a fulfilled case has every
   need met and only waits to be closed. This is the set the network feed already uses.
3. **Which data refreshes?** Proposed: the data `StaffProvider` already holds, plus cases and transfers. Pages with their own
   loader keep loading once. Reason: "every page benefits" only holds for the shared data. Moving each page to the refresh
   is a separate change.
4. **How often does the data refresh?** Proposed: every 30 seconds, paused while the tab is hidden. Reason: ER staff need the
   figures to be current within about a minute, and 30 seconds keeps the load on the server low.
5. **Does the pharmacist see the Transfers tile?** Proposed: no. Reason: B01 gives the pharmacist no access to transfers.
6. **Who sees the "waiting for an answer" count?** Proposed: everyone who sees the tile sees the same hospital-wide count,
   with neutral wording. Reason: a doctor can't approve blood or equipment, so "waiting for your answer" would be wrong for
   them. The count still shows that a supplier has a request open.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
