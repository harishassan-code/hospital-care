---
id: B06
title: Notification service
issues: 52
points: 5
priority: high
sprint: 8
depends_on: -
owner: unassigned
status: Ready
---

# B06 · Notification service

**Goal:** Staff get in-app notifications for requests, approvals and status changes at their hospital, through a channel abstraction that can add email/SMS later.

## Stories and acceptance criteria

[#52](https://github.com/harishassan-code/hospital-care/issues/52): As staff, I want to be notified of requests, approvals and status changes relevant to my hospital so
that I can act quickly.

- [ ] In-app notifications with read/unread state
- [ ] Channel abstraction so email/SMS can be added later
- [ ] Notifications created from domain events

## Build on

- `backend/apps/notifications/`: empty app, already installed.
- Domain events that exist today: case created / escalated (`apps/emergencies/services.py`,
  `escalate_overdue_cases`), reservation made / released / expired (`apps/matching/reservations.py`), allocation
  (`apps/matching/allocations.py`). Transfers (B01–B03) add their events as they land.
- `apps.audit.services.record` is already called at each of these points: a single `notify(...)` call next to it keeps
  events in one place.

## Scope

- **In:** Notification model (recipient hospital + role or user, kind, severity, link, read_at), `Channel` interface with an in-app channel, events wired for emergencies and reservations, list / unread-count / mark-read API.
- **Out:** The bell and banner UI (B07); email/SMS delivery.

## Open questions for Inception

- Recipient = a user, or a hospital + role (fan-out on read)? Fan-out on read is simpler and scales with staff changes.
- Which events are *critical* (banner in B07)? Suggest: new critical case, escalation, transfer request received.

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-notification-service.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-notification-service.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-notification-service.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
