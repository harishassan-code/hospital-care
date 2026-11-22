# Inception Spec: Notification service

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B06](../bolts/B06-notification-service.md)
**Related backlog items:** #52 [Notification service](https://github.com/harishassan-code/hospital-care/issues/52)
(Sprint 8). Its bell and banner UI is #53 [In-app alerts UI](https://github.com/harishassan-code/hospital-care/issues/53)
([B07](../bolts/B07-alerts-ui.md)), which builds on this spec. Builds on #47 [transfer request](2026-11-18-transfer-request.md),
#48 [transfer tracking](2026-11-18-transfer-tracking.md), #49 [delivery confirmation](2026-11-18-delivery-confirmation.md),
#35 [request escalation and closure](2026-11-17-request-escalation-and-closure.md) and #43
[atomic resource reservation](2026-11-17-atomic-resource-reservation.md).

## Problem

Staff only see a change when they open the page where it happened. A critical case escalates, a supplier gets a transfer
request, or a hold runs out, and the person who has to act may be on another page, or on another ward. Today the only
record of these events is the audit log, which nobody reads during a shift.

This is for staff at each hospital, by role: the emergency coordinator at the case's hospital (doctor or nurse), the blood
bank or nurse at the supplying hospital who answers a transfer, and anyone who follows a case.

## User stories

- As staff, I want to be notified of requests, approvals and status changes relevant to my hospital so that I can act
  quickly. (#52)

## Acceptance criteria

### Model

- [ ] `Notification` (`apps/notifications/models.py`) has: `user` (one recipient), `kind` (the event, e.g. `transfer.requested`),
      `severity` (`critical` or `info`), `message` (up to 300 characters), `link` (a staff page path), `created_at`, and
      `read_at` (empty until read).
- [ ] One row per recipient. Read state belongs to one person, so a row can't be shared (see open question 1).
- [ ] Rows are created only by `notify`. The API never edits or deletes them, except for `read_at`. The Django admin shows
      them read-only.
- [ ] Index on `(user, read_at)` for the unread count.
- [ ] `docs/architecture/erd.md` is updated to match. Today it has `user_id`, `event` and `read`.

### One service call

- [ ] `apps.notifications.services.notify(kind, *, hospital, module, message, link, severity="info", actor=None)` creates one
      row per recipient and returns them. If `hospital` is `None`, it creates nothing.
- [ ] Recipients are active users whose `hospital` is `hospital` and whose role can edit `module` (`can_edit` on the `ACCESS`
      table in `apps/accounts/permissions.py`). `actor` is left out.
- [ ] Domain code passes the hospital and the module. It never picks recipients or channels. `apps.notifications` imports
      nothing from the domain apps, so there are no import cycles.
- [ ] `notify` runs inside the same transaction as the move it reports, next to `record(...)`. If the move rolls back, no
      notification is kept.
- [ ] `notify` hands each new row to every channel in `CHANNELS`. The only channel is `InAppChannel`, which does nothing
      beyond the stored row. An email or SMS channel is one new class and one entry in `CHANNELS`.

### Events

- [ ] Case created with severity critical: `critical`, to the case side. Other new cases notify nobody.
- [ ] Case moved to **escalated**, automatically or by hand: `critical`, to the case side. Hook: `move_case`, when the action
      is `escalate`.
- [ ] Reservation made at the case's own hospital: `info`, case side. Hook: `reserve`.
- [ ] Reservation released or expired at the case's own hospital: `info`, case side. Hook: `_end`, which both paths use.
- [ ] Transfer requested: `critical`, supplier side.
- [ ] Transfer approved, rejected or dispatched: `info`, case side.
- [ ] Transfer delivered or cancelled: `info`, supplier side.
- [ ] Transfer moved to in transit: nobody. Dispatched already tells the case side.
- [ ] A hold at another hospital (an approved transfer's hold at the supplier) notifies nobody. The transfer event covers it.

### Endpoints

- [ ] `GET /notifications/` returns 200 `Notification[]`: the signed-in user's 50 newest rows, newest first. `?unread=true`
      returns only unread rows.
- [ ] `GET /notifications/unread-count/` returns 200 `{count}`.
- [ ] `POST /notifications/<id>/read/` returns 200 `Notification` with `readAt` set. A second call returns 200 with the first
      `readAt`, unchanged.
- [ ] A row that belongs to another user is 404, as if it didn't exist.
- [ ] Signed out: 403. A patient: 403. A staff user with no hospital (an admin without one): 200 with an empty list.
- [ ] `Notification` is camelCase: `{id, kind, severity, message, link, createdAt, readAt}`, with `readAt` `null` until read.

### Permissions and audit

- [ ] A permission class `IsStaff`: signed in, and `effective_role` in `STAFF_ROLES`. A notification is personal, not a
      module, so there is no new row in `ACCESS`. `ACCESS` and `roles.ts` don't change.
- [ ] Notification rows are not audit-logged: each copies an event that already has its audit record. Marking a
      notification read is a state change, so the read endpoint writes `notification.read` (open question 3).

### Tests

- [ ] Each event above reaches the right users and nobody else: not another hospital, not the actor, not a role without
      edit on the module.
- [ ] A move that rolls back leaves no notification behind.
- [ ] A hold at another hospital notifies nobody.
- [ ] Each endpoint has tests for 200, for 403 (signed out, patient) and for 404 (another user's row).
- [ ] The response shapes match the contract above, so B07 can mock them in `src/test/mockApi.ts`. B06 changes no frontend code.

## The rules in one place

| Thing | Rule |
|---|---|
| Recipients | Active users at the hospital whose role has edit on the module. The actor is left out. Users with no hospital get nothing, including admins without one. |
| Case side | Hospital: the case's hospital. Module: `emergencies`. Roles: doctor and nurse, plus admin if their hospital is set. Blood bank and pharmacist get no case notifications. |
| Supplier side | Hospital: the supplying hospital. Module: the resource's module (`blood` or `equipment`). Blood bank gets blood, nurses get equipment. This is the same rule as who may answer a transfer (B01). |
| Transfer rule | Each move notifies the side that did not make it. Requested and cancelled are made by the requester, so the supplier hears. Approved, rejected and dispatched are made by the supplier, so the case side hears. Delivered is made by the requester, so the supplier hears. |
| Reservation rule | Only holds at the case's own hospital notify. |
| Severity | `critical`: a critical case created, a case escalated, a transfer requested. Everything else is `info`. |
| Read | `readAt` is set once. A repeat call keeps the first time. |
| List | Own rows only: 50 newest by `createdAt`. No pagination in MVP. |
| Keeping rows | Not pruned in MVP. |
| Link | A relative staff path. A case is `/staff/emergencies/<reference>`. A transfer is `/staff/transfers`. |
| Audit | Notification rows are not audit-logged; marking one read writes `notification.read` (open question 3). |

## Non-goals

- Email, SMS, push, or any channel other than in-app. The channel class is the hook for them later.
- Websockets or live push. Polling is B07's choice.
- The bell, the banner and the acknowledge button (B07, #53). B06 changes no frontend code.
- Warnings that a hold is about to expire. The bolt asks for the *expired* event only. The expiry sweep runs when someone
  reads, so a warning would often come too late, and it needs a scheduler first.
- Allocation events. The bolt lists allocation as a source, but its Scope names emergencies and reservations. Add it later as
  one call next to `record`.
- In-transit moves, ambulance trips (B05), patient transfer (B17), pharmacy stock, and low-stock or expiring-unit alerts (B07
  already computes those in the browser).
- Notifying patients, or anyone outside staff.
- Mark all as read, delete, snooze, grouping of repeated events, and per-user settings.
- Pruning old rows, and a scheduler for the sweeps. The request-time sweeps keep their current form.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Is the recipient a user, or a hospital and role (fan-out on read)?** Proposed: a user per row, written when the event
   happens (fan-out on write). The hospital and role decide who gets the row. Reason: `readAt` belongs to one person, so
   fan-out on read would need a second table for read state, which is more code. The cost is that someone who joins later
   sees only events from then on. This changes the bolt's Scope wording: the model holds a user, not a hospital and role.
2. **Which events are critical?** Proposed: a critical case created, a case escalated and a transfer requested, as the bolt
   suggests. Reason: these need an answer soon. Everything else is `info`, which shows in the list but not in B07's banner.
3. **Should notifications and read marks be audit-logged?** Proposed: the rows no, the read marks yes. A notification
   copies an event that is already logged, so logging it again adds no facts. Marking one read is a state change, and an
   acknowledged critical alert may need explaining later, so the read endpoint writes `notification.read` (as AGENTS asks
   and as [the alerts UI spec](2026-11-18-alerts-ui.md) assumes).

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
