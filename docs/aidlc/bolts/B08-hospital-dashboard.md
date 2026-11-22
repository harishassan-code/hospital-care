---
id: B08
title: Hospital dashboard: requests, transfers and live refresh
issues: 54
points: 3
priority: high
sprint: 8
depends_on: B01
owner: codewithalphadotcom
status: In Review
---

# B08 · Hospital dashboard: requests, transfers and live refresh

**Goal:** Finish the hospital dashboard: the Overview page already shows beds, blood by group, pharmacy and attention items; add open emergency requests and pending transfers, and refresh without a page reload.

## Stories and acceptance criteria

[#54](https://github.com/harishassan-code/hospital-care/issues/54): As hospital staff, I want a dashboard of my inventory, beds, active requests and transfers so that I
see my situation at a glance.

- [x] Shows stock by blood group, bed occupancy (already on Overview)
- [ ] Shows open requests and pending transfers
- [ ] Refreshes without page reload

## Build on

- `frontend/src/pages/staff/OverviewPage.tsx` and its tiles; `frontend/src/features/staff/StaffProvider.tsx` holds the
  loaded data. Add a refresh interval there so every page benefits.
- `GET /api/emergencies/` for open cases; the transfers list from B01/B02.

## Scope

- **In:** Two new tiles/panels, periodic refresh, tests.
- **Out:** City-wide view (B09).

## Open questions for Inception

- Points re-estimated from 5 to 3 because most of the story already shipped; confirm at planning.

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-hospital-dashboard.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-hospital-dashboard.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-hospital-dashboard.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
