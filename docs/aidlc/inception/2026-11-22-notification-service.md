# Inception Spec: Notification service

**Date:** 2026-11-22
**Author:** Claude, drafted for review
**Bolt:** [B06](../bolts/B06-notification-service.md)
**Related backlog item:** #52

## Problem

Staff only find out about a new critical case, an escalation or an incoming transfer request by opening the right page.
Supplier hospitals in particular miss transfer requests.

## User stories

- As staff, I want to be notified of requests, approvals and status changes relevant to my hospital, so that I can
  act quickly. (#52)

## Acceptance criteria

- [ ] A notification has a recipient **hospital + set of roles** (empty = all staff roles), a kind, a severity (info /
      warning / critical), a title, a body, a link (frontend path) and a created time.
- [ ] Read state is **per user** (a `NotificationReceipt` row), so one nurse reading it doesn't hide it from another.
      Critical notifications also record a per-user **acknowledged** time (used by B07's banner).
- [ ] `notify(...)` in `apps/notifications/services.py` sends through a list of channels; only `InAppChannel` exists.
      A `Channel` base class with `send(notification)` is the extension point for email or SMS.
- [ ] Events wired: case created (critical if severity is critical), case escalated (critical), transfer requested
      (critical, to the supplier), transfer approved / rejected / dispatched / received (info, to the other side),
      reservation expired (warning).
- [ ] API: `GET /api/notifications/` (mine, newest first, `?unread=1`), `GET /api/notifications/unread-count/`,
      `POST /api/notifications/<id>/read/`, `POST /api/notifications/read-all/`,
      `POST /api/notifications/<id>/acknowledge/`. Authenticated staff only; you see only your hospital's
      notifications for your role (admins: every hospital's notifications addressed to admins).
- [ ] Notifying never breaks the action that caused it: an error in a channel is logged, not raised.

## Non-goals

- UI (B07). Email/SMS delivery. Push/WebSockets. User preferences.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Recipient = a user, or a hospital + role?** Proposed: hospital + roles (fan-out on read), with per-user read rows.
2. **Which events are critical?** Proposed: new critical case, escalation, transfer request received.
3. **Audit-log notifications?** Proposed: no. They come from events that are already audited.

## Approval

- [x] Approved by: kabirraj0011 (for the Product Owner) on 2026-11-22
