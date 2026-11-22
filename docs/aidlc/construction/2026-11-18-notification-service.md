# Construction Plan: Notification service

**Spec:** [docs/aidlc/inception/2026-11-18-notification-service.md](../inception/2026-11-18-notification-service.md)
**Date:** 2026-11-18

B06 is the backend only. The model, one `notify` call, the events, and the list, count and mark-read API. The bell and
banner (B07) build on the API later. Everything hangs off one function, so the events stay in one place.

## Design

### Model (`backend/apps/notifications/models.py`)

- `Notification`: `user` (FK, CASCADE, `related_name="notifications"`), `kind` (max 40), `severity` (`critical` or
  `info`, a `TextChoices`), `message` (max 300), `link` (max 200, blank), `created_at` (default now), `read_at` (null).
  Ordering `-created_at, -id`. Index `(user, read_at)`.
- Admin: every field read-only, no add, no change, no delete.

### Service (`backend/apps/notifications/services.py`, `channels.py`)

- `notify(kind, *, hospital, module, message, link, severity="info", actor=None) -> list[Notification]`.
  Recipients: active users whose `hospital` is `hospital` and whose role can edit `module` (`ACCESS`). Admins count as
  their effective role (superusers). The actor is excluded. `hospital=None` creates nothing. One `bulk_create`, then
  each new row goes to every channel in `CHANNELS`.
- `Channel` (a base class with `send(notification)`), `InAppChannel` (a no-op: the row is the delivery), and
  `CHANNELS = (InAppChannel(),)`.
- `inbox(user, unread_only)`, `unread_count(user)`, `mark_read(pk, user)`. `mark_read` locks the row, sets `read_at`
  once and writes `notification.read` on that first set only. A second call returns the row unchanged.
- The app imports only `apps.accounts` (ACCESS, STAFF_ROLES) and `apps.audit`. No domain app, so no cycles.

### Hooks (the events in the spec, all inside the moves' transactions)

| Where | Event | Kind | Severity | Side |
|---|---|---|---|---|
| `emergencies.create_case` | case created, critical only | `case.created` | critical | case |
| `emergencies.move_case` when action is `escalate` | case escalated (hand or automatic) | `case.escalated` | critical | case |
| `matching.reserve` when the hospital is the case's own | hold(s) made | `reservation.created` | info | case |
| `matching._end` when the hospital is the case's own | released / expired | `reservation.released` / `reservation.expired` | info | case |
| `transfers.request_transfer` | transfer requested | `transfer.requested` | critical | supplier |
| `transfers._move` for approve, reject, dispatch | answered, shipped | `transfer.<status>` | info | case |
| `transfers._move` for cancel, deliver | cancelled, received | `transfer.<status>` | info | supplier |

`_move` does not notify for `startTransit`. Holds at another hospital notify nobody (the case-own check in `reserve`
and `_end`). `reserve` notifies once per call, not once per unit, so a five-unit hold is one bell entry.

### API (`backend/apps/notifications/urls.py`, mounted at `/api/notifications/`)

| Method | Path | Does |
|---|---|---|
| GET | `/api/notifications/?unread=true` | The user's 50 newest, newest first. Only unread with `unread=true` (or `1`). |
| GET | `/api/notifications/unread-count/` | `{count}` |
| POST | `/api/notifications/<id>/read/` | Sets `read_at` once. 404 for another user's row. |

Permission class `IsStaff` (in `apps/accounts/permissions.py`): signed in, and `effective_role` in `STAFF_ROLES`.
Patients and signed-out users get 403. No row in `ACCESS`, and `roles.ts` does not change.

### Frontend (only what B07 needs)

- `src/api/notifications.ts`: types and three calls. Unit test in `src/api/notifications.test.ts`.
- `src/test/mockApi.ts`: `notifications` seed option and the three routes.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Model, migration, read-only admin | `apps/notifications/{models,admin}.py`, migration `0001` | `test_api.py` (admin read-only), model index via the list |
| 2 | Service, channels, `IsStaff` | `apps/notifications/{services,channels}.py`, `apps/accounts/permissions.py` | `test_notify.py` (recipients, channels) |
| 3 | Hooks in the domain moves | `apps/emergencies/services.py`, `apps/matching/reservations.py`, `apps/transfers/services.py` | `test_events.py` (each event, rollback) |
| 4 | API | `apps/notifications/{serializers,views,urls}.py`, `config/urls.py` | `test_api.py` (200, 403, 404, shapes, audit) |
| 5 | Frontend client and mock | `src/api/notifications.ts`, `src/api/notifications.test.ts`, `src/test/mockApi.ts` | the client test |
| 6 | Docs | `docs/architecture/api.md`, `erd.md`, `api-contracts.md` (IsStaff note) | the CI checks |

## Sequencing

1 → 2 → 3 → 4 → 5 → 6. Units 3 and 4 can land in either order once 2 is in. Unit 5 needs 4's shapes.

## Test plan

- Recipients: by hospital and role; another hospital, the actor, an inactive user, a role without edit on the module,
  a patient, and an admin without a hospital are all left out.
- Each event above reaches the right side and nobody else (case side vs supplier side; the actor is left out).
- Non-critical case creation notifies nobody. Automatic and manual escalation both notify.
- A hold at another hospital (a transfer's approval, its cancel) notifies nobody.
- A move that rolls back leaves no notification: an escalation in a rolled-back transaction, and a receipt that the case
  refuses.
- API: 200 list (newest first, 50 cap, unread filter), unread count, mark read (first call sets `readAt`, second keeps it,
  one `notification.read` audit row), 404 for another user's row, 403 signed out and for a patient, 200 empty for an admin
  without a hospital, exact camelCase keys.
- CI: the three check commands in `AGENTS.md`, plus `npm run lint`, `npm test`, `npm run build`, and the root checks.

## Decisions to confirm

- `unread` accepts `true` and `1` (B06 says `true`, B07 says `1`). `false`, `0` or no value returns all. Anything else is 400.
- A repeat mark-read writes no audit row, since nothing changes.
- One notification per `reserve` call, not per unit.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that
approval is the Construction gate.
