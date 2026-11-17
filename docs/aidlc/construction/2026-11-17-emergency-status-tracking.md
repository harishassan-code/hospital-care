# Construction Plan: Emergency request status tracking

**Spec:** [docs/aidlc/inception/2026-11-17-emergency-status-tracking.md](../inception/2026-11-17-emergency-status-tracking.md)
**Date:** 2026-11-17

## Design

- **Lifecycle:** `REQUEST_LIFECYCLE = StateMachine("case", RequestStatus, {...})` in `models.py`, the same
  `StateMachine` the beds and blood units use. The table is the one in the spec. `closed` and `cancelled` have no
  outgoing entries, so `next()` refuses everything from them.
- **History:** a `RequestStatusChange` model: `request` (FK, CASCADE, `related_name="history"`), `from_status` (blank
  for the first entry), `to_status`, `action`, `note` (TextField, blank; the serializer caps it at 500), `actor` (FK
  user, SET_NULL, so a removed user keeps their entries), `at` (default now). Ordered by `at`, then `id`.
- **Migration `0004_request_status_history`:** a `CreateModel`, then a `RunPython` that writes one `create` entry per
  existing case (from `""` to `open`, `at` = `created_at`, `actor` = `created_by`). The reverse is a no-op: reversing
  the `CreateModel` drops the table.
- **Opening a case:** `create_case` writes the first entry in the same transaction as the case.
- **Moving a case:** `apply_case_action(reference, action, note, actor)` in `services.py`. Inside `transaction.atomic`
  it takes the row lock (`select_for_update`), returns 404 when the case is missing or `may_change` refuses it, asks
  `REQUEST_LIFECYCLE.next()` for the new status (raising `TransitionNotAllowed` saves nothing), saves the status, writes
  the history entry and the audit record (`emergencyrequest.status_changed`, before and after the status,
  `reason = note or action`).
- **Why not `change_status`:** it is the resources helper, but it sets `status_since`, a field this model does not
  have, and it has no place to write the history entry. The new service uses the same two steps, `next()` and
  `record()`, directly.
- **Audit reason length:** `apps.audit.services.record` keeps 300 characters of `reason`. The history entry keeps the
  whole note (up to 500).
- **API:** `POST /api/emergencies/<reference>/actions/` checks `{action}` against the table (unknown → 400), then
  calls the service (refused → 409, `{detail}` in the same shape as beds). The detail GET adds `history` and
  `actions` (the moves valid from the current status, in the table's order). The list is unchanged, with no history.
- **Frontend:** `/staff/emergencies/:reference` renders the case, its needs and the timeline in `<ol>` with
  `<time dateTime>`. Move buttons come from `actions`, with an optional note. Labels and the transition mirror live
  in `features/emergencies/emergencies.ts`, which the mock API uses to apply moves the way the server does.
- **Admin:** `status` becomes read-only in the Django admin. Before this, an admin could set any status by hand, which
  skipped the lifecycle and the history.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend: `REQUEST_LIFECYCLE`, `RequestStatusChange` and migration `0004` (create + backfill), first entry on create, the action endpoint, `history` and `actions` on the detail, admin status read-only, API docs | `backend/apps/emergencies/{models,services,serializers,views,case_urls,admin}.py`, `backend/apps/emergencies/migrations/0004_request_status_history.py`, `backend/apps/emergencies/tests/test_status.py`, `docs/architecture/api.md` | pytest: every allowed move (parametrized); refused moves → 409 with nothing saved and no entry; terminal statuses refuse every action; unknown action → 400; view-only role → 403; another hospital's case → 404; staff with no hospital → 404; admin elsewhere → 200; create writes the first entry; each move writes entry and audit with actor and note; note over 500 → 400; detail history order and `actions`; list has no history; backfill via importlib |
| 2 | Frontend: API types and calls, labels and transition mirror, case page at `/staff/emergencies/:reference`, references link from the list, mock routes, route in `App.tsx` | `frontend/src/api/emergencies.ts`, `frontend/src/features/emergencies/emergencies.ts`, `frontend/src/pages/staff/EmergencyCasePage.tsx` (+ `.test.tsx`), `frontend/src/pages/staff/EmergenciesPage.tsx` (+ test), `frontend/src/App.tsx`, `frontend/src/test/mockApi.ts` | vitest: timeline renders oldest first; only valid move buttons show; a move with a note updates the status and the timeline; a 409 shows an alert; a view-only role sees no move buttons; the list links each reference to its page |

## Sequencing

Unit 1 before unit 2: the frontend types and mock routes follow the API contract that unit 1 makes real.

## Test plan

- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && pytest`
  on SQLite and on Postgres.
- Migrations forward, back and forward on a fresh SQLite database: `migrate`, `migrate emergencies 0003`, `migrate`.
- `cd frontend && npm run lint && npm test && npm run build`
- Manual: sign in as `doctor@demo.citycare.pk`, open a case, move it open → matching → fulfilled with a note, and
  check the timeline. Then try a refused move through the API and confirm it answers 409.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified:** SQLite, full suite: 314 passed and one failure that is not this story's (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, a known SQLite issue). Postgres: 315 passed. Ruff check and format, and `makemigrations --check`, clean. Migrations on a fresh SQLite file: migrate, back to 0003, forward, with two cases inserted at 0003 that each got a creation entry from the backfill. Frontend: lint clean, 287 tests pass, build succeeds.
- **A rollback loses the timeline.** Reversing 0004 drops the history table. As with #31's round trip, this is accepted: the audit log still holds every move.
- **The actor is the name, or the email when there is no name.** The spec said "full name". This follows the case's existing `createdBy` rule, so a user without a name shows their email rather than nothing.
- **Admin edits can no longer skip the lifecycle.** `status` is read-only in the Django admin. Before this story an admin could set any status by hand, with no timeline entry.
- **The audit reason is cut to 300 characters** by the shared audit helper. The timeline keeps the whole note (up to 500).
- **Admins at another hospital:** a move succeeds (200), but the page's GET returns 404 for the same case. This is open question 4 in the inception spec.
- **`docs/architecture/erd.md` is not updated.** It does not show `RequestStatusChange` yet. Add it with the next ERD change.
