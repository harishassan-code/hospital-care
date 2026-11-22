---
id: B07
title: In-app alerts UI
issues: 53
points: 3
priority: medium
sprint: 8
depends_on: B06
owner: codewithalphadotcom
status: In Review
---

# B07 · In-app alerts UI

**Goal:** The bell shows server notifications with an unread count, and critical alerts stay as a banner until someone acknowledges them.

## Stories and acceptance criteria

[#53](https://github.com/harishassan-code/hospital-care/issues/53): As staff, I want a notification bell and alert banners for critical events so that urgent items are not missed.

- [ ] Unread count badge
- [ ] Critical alerts shown as a banner until acknowledged

## Build on

- The bell already exists in `frontend/src/features/staff/StaffLayout.tsx` and counts items computed in the browser by
  `frontend/src/features/staff/attention.ts` (low stock, expiring units, slow bed cleaning). Merge server
  notifications into it rather than adding a second bell.
- `frontend/src/test/mockApi.ts` to mock the new endpoints for tests.
- Remove `/staff/alerts` from `planned.ts` if you add an alerts page.

## Scope

- **In:** Unread badge from the API, notifications list in the bell, critical banner with acknowledge, polling.
- **Out:** Push/WebSockets (polling is enough for the MVP).

## Open questions for Inception

- Polling interval (30 s?) and whether to pause it when the tab is hidden.

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-alerts-ui.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-alerts-ui.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-alerts-ui.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
