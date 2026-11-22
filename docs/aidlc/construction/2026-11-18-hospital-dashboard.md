# Construction Plan: Hospital dashboard: open requests, transfers and live refresh

**Spec:** [docs/aidlc/inception/2026-11-18-hospital-dashboard.md](../inception/2026-11-18-hospital-dashboard.md)
**Date:** 2026-11-18

No backend change: both tiles read the existing `GET /api/emergencies/` and `GET /api/transfers/?direction=` list
endpoints. The work is frontend, in the staff workspace that already loads the Overview's data.

## Design

### Rules (`frontend/src/features/overview/requests.ts`)

One pure function, `summarizeRequests(cases, transfers)`, holds every count the two tiles show:

- Open case: status `open`, `matching`, `partiallyFulfilled` or `escalated`. `openCases` counts them; `criticalCases`
  counts the open ones with severity `critical`.
- Pending transfer: status `requested`, `approved`, `dispatched` or `inTransit`. Counted once by id, because an admin's
  two lists are the same network-wide list (the API ignores `direction` without a hospital).
- To answer: incoming transfers with status `requested`. Outgoing: pending transfers in the outgoing list.
- A `null` input (the call failed, or the role can't see it) gives `null` for that part, so the tile shows "Unavailable".

### Data and refresh (`frontend/src/features/staff/StaffProvider.tsx`, `staffContext.ts`)

- `StaffData` gains `cases` (`EmergencyCase[] | null`) and `transfers` (`{ incoming, outgoing } | null`, null when the
  role can't see transfers or the call failed on the first load).
- A `loadStaffData(role)` function makes the same calls as today, plus the two new ones. Beds, blood and pharmacy failing
  on the first load still shows `StaffDataState`. Cases, transfers and the public ER status are optional: a failure
  leaves that part `null`.
- Reload is all-or-nothing. A reload whose calls all succeed replaces the data and sets `updatedAt`. Any failed call
  keeps the data on screen and sets `refreshFailed`; the next tick tries again. A first load that is partial is accepted.
- An interval every 30 seconds calls `reload`. It returns early when the tab is hidden (`document.visibilityState`) and
  when a reload is already running (a ref), so two never overlap. A `visibilitychange` to visible reloads once. The
  interval and the listener are cleared on unmount.
- `StaffState` gains `updatedAt` and `refreshFailed`. `setData` becomes a single helper used by the bed, blood and
  reload paths. Nothing sets `loading` again after the first load, so open forms and dialogs stay mounted.

### Overview (`frontend/src/features/overview/StatusTiles.tsx`, `LastUpdated.tsx`)

- Tile order: Beds, Emergency, **Open requests**, **Transfers** (only when the role can see transfers), Blood bank,
  Pharmacy.
- Open requests: value = open cases; unit "open case(s)"; badge critical "N critical" or ok "None critical"; link
  `/staff/emergencies`. Visible to every role. Unavailable: detail "Unavailable", neutral badge "Check the Emergencies
  page".
- Transfers: value = pending transfers; detail "N to answer · M outgoing"; badge warning "N waiting for an answer" or ok
  "Nothing to answer"; link `/staff/transfers`. Unavailable: detail "Unavailable", neutral badge "Check the Transfers
  page".
- `LastUpdated` renders a `role="status"` paragraph above the tiles: "Updated HH:MM", or "Couldn't update. Showing data
  from HH:MM." after a failed reload. Words carry the state, not colour.

### Access

Open requests: all five roles (`canSee(role, 'emergencies')`). Transfers: `canSee(role, 'transfers')`, which is admin,
doctor, nurse and blood bank. The pharmacist's workspace makes no `/transfers/` call. No buttons on the dashboard.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Pure rules: open, critical, pending, to answer, unavailable | `features/overview/requests.ts` (new) | `features/overview/requests.test.ts` (new) |
| 2 | Shared data and live refresh: new calls, interval, visibility, no overlap, failure keeps data | `features/staff/StaffProvider.tsx`, `features/staff/staffContext.ts` | `features/staff/StaffProvider.refresh.test.tsx` (new): fake timers, visibility, overlap, failed reload, same calls per role, no "Loading…" on reload |
| 3 | Overview: two tiles, "Updated" line, tile list | `features/overview/StatusTiles.tsx`, `features/overview/LastUpdated.tsx` (new), `features/overview/Overview.module.css`, `pages/staff/OverviewPage.tsx` | `pages/staff/OverviewPage.test.tsx`: tiles per role, unavailable states, updated line, tile list |
| 4 | Mock API | `test/mockApi.ts` (existing `GET /emergencies/` and `GET /transfers/` already answer both directions in the B01 shape; no change expected) | used by units 2 and 3 |
| 5 | Docs | `docs/architecture/api.md` (the staff workspace reloads its data every 30 seconds through the existing GET calls) | – |

## Sequencing

1 → 2 → 3, then 4 and 5 with them. Unit 1 has no dependency. Unit 3 needs the new `StaffData` fields from unit 2.

## Test plan

- Unit tests for the rules: every open and pending status, the critical rule, to answer vs outgoing, admin de-duplication,
  and `null` (unavailable) for each side.
- Overview tests per role: admin, doctor, nurse, blood bank see both tiles with the expected counts; pharmacist sees
  Open requests and no Transfers tile and makes no `/transfers/` call. The tile list test is updated for the new order.
- Unavailable: transfers call fails on the first load, so the Transfers tile says Unavailable and the other tiles show.
  Cases call fails, so Open requests says Unavailable.
- Refresh with fake timers: a reload after 30 seconds (not before); no reload while the tab is hidden; a reload once
  when it becomes visible; no second reload while one is in flight; a failed reload keeps the data, shows the
  "Couldn't update" line and the next tick recovers; reload makes the role's calls only; reload does not show "Loading…"
  and keeps local state in a child.
- CI: the three check commands in `AGENTS.md`, backend and frontend, and the root checks.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that
approval is the Construction gate.
