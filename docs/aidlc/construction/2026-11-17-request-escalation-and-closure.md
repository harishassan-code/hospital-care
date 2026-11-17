# Construction Plan: Request escalation and closure

**Spec:** [docs/aidlc/inception/2026-11-17-request-escalation-and-closure.md](../inception/2026-11-17-request-escalation-and-closure.md)
**Date:** 2026-11-17

## Design

- **Setting:** `EMERGENCY_ESCALATION_MINUTES` in `backend/config/settings.py`, read by a small helper
  `positive_int_env(name, default)`. It raises `ImproperlyConfigured` for anything that is not a whole number of 1 or
  more, so a bad value stops the server at startup. Documented in `backend/.env.example` and
  `docs/setup/deployment.md`.
- **One move function:** `apply_case_action` in `services.py` is split. The core step, "move the status, write the
  timeline entry, write the audit record", becomes `_move(case, action, *, note, actor, at)`. Both the manual action and
  the automatic escalation call it. `apply_case_action` keeps the lock, the 404 and the close-note check; the automatic
  path keeps its own lock and re-check.
- **Overdue query:** `EmergencyRequest` annotated with `Max("history__at")`, filtered to critical, active and
  `entered < now - N minutes`. One query. When it returns nothing, `escalate_overdue` returns 0.
- **Automatic escalation:** `escalate_overdue(now=None) -> int` in `services.py`. It takes the candidate ids from the
  query above, then in `transaction.atomic()` locks them with `select_for_update(skip_locked=True)`, re-checks severity,
  status and the latest entry time for the locked rows, and calls `_move(..., action="escalate", actor=None,
  note=f"Not fulfilled within {N} minutes (automatic)")`. Two concurrent runs cannot escalate the same case: the second
  skips a locked row, and an escalated row no longer matches the status filter. On SQLite, Django ignores `FOR UPDATE`
  entirely, so `skip_locked` is never sent there.
- **Triggers:** the management command `escalate_overdue_cases` (in `apps/emergencies/management/commands/`) prints
  the count. The case list and case detail GET views call `escalate_overdue()` first, with a `ponytail:` comment naming
  the ceiling: a request-time sweep, to move to a scheduled job when read traffic or case volume grows.
- **Close rule:** `apply_case_action` raises `OutcomeNoteRequired` when the action is `close` and the note is blank
  after trimming. It checks this before the lifecycle, after the case is found. The view answers 400
  `{"note": ["Add an outcome note to close the case."]}`. Nothing is saved.
- **Outcome:** `CaseDetailSerializer` gets `outcome`: the note of the latest `close` entry, or `null`. It reads the
  prefetched history, so it adds no query.
- **Frontend:**
  - Choosing "Close case" opens an outcome form with a required textarea. The native `required` attribute and a
    client check (non-blank) both run before the request. A 400 with `note` shows on that field.
  - A closed case shows an "Outcome" panel with the note.
  - A null actor in the timeline shows "System".
  - The list and case page show escalated cases as a `StatusBadge` with the text "Escalated". The badge's icon
    carries the meaning as well as its colour.
  - The mock API answers 400 for a close without a note, computes `outcome`, and returns history entries with a null
    actor when a case is escalated by the system.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend: the setting and its helper, `_move` refactor, `escalate_overdue`, the command, the request-time triggers, the close rule, `outcome` on the detail, API docs and setting docs | `backend/config/settings.py`, `backend/.env.example`, `backend/apps/emergencies/{services,serializers,views}.py`, `backend/apps/emergencies/management/commands/{__init__,escalate_overdue_cases}.py`, `backend/apps/emergencies/tests/test_escalation.py`, `docs/architecture/api.md`, `docs/setup/deployment.md` | pytest: escalates only critical, active, overdue cases; history and audit with no actor; fresh window after resume; idempotent; setting honoured with `override_settings`; command prints the count; list and detail GET trigger escalation; close without note, or with whitespace, is 400 and changes nothing; close with a note is closed, with the note in history and `outcome`; `outcome` null otherwise; the parsing helper accepts and refuses values |
| 2 | Frontend: API type for `outcome`, close form and outcome panel on the case page, "System" for a null actor, "Escalated" badge in the list and on the page, mock API updates | `frontend/src/api/emergencies.ts`, `frontend/src/pages/staff/EmergencyCasePage.tsx` (+ `.test.tsx`), `frontend/src/pages/staff/EmergenciesPage.tsx` (+ test), `frontend/src/test/mockApi.ts` | vitest: close needs an outcome (no request without it, and a whitespace note is refused on the page); a server 400 shows on the field; a closed case shows its outcome; a null actor shows "System"; an escalated case is labelled "Escalated" in the list and on the page |

## Sequencing

Unit 1 before unit 2: the frontend's `outcome` field and the 400 shape follow the API that unit 1 makes real.

## Test plan

- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && pytest`
  on SQLite and on Postgres.
- The command on Postgres: `python manage.py migrate -v0 && python manage.py escalate_overdue_cases`.
- `cd frontend && npm run lint && npm test && npm run build`
- Manual: set `EMERGENCY_ESCALATION_MINUTES=1`, open a critical case, wait a minute, reload the list. The case shows
  "Escalated" with a "System" entry. Close it without a note (refused) and then with one.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified:** SQLite, full suite: 367 passed and one failure that is not this story's (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, a known SQLite issue). Postgres: 368 passed. Ruff check and format, and `makemigrations --check`, clean. The command on Postgres (`migrate`, then `escalate_overdue_cases`) prints `Escalated 0 overdue cases.` Frontend: lint clean, 296 tests pass, build succeeds.
- **Skip-locked on SQLite.** Django only sends `FOR UPDATE` on a backend that supports it, and checks `skip_locked` inside that branch, so SQLite never sees it. No gate is needed. The overdue tests run `skip_locked` on both databases.
- **Close checks the lifecycle first.** A close with no note on a case that is already closed is 409 ("Can't close a case that is closed."), not 400. The note is only asked for when the move itself is allowed.
- **The detail's query count is 6, not 5.** The overdue check is one query when nothing is overdue, so the pin in `test_availability.py` moved with a comment.
- **No `DATABASE_URL` startup check exists.** The story said `settings.py` has one to copy. It does not, so `positive_int_env` is the only startup validation in settings.
- **A removed user's entries also show "System".** Their actor is null too (the `SET_NULL` rule), so they read the same as an automatic escalation. Open question 3 in the spec. The previous text, "A former staff member", is gone.
- **The outcome is a single-line field.** The app has no textarea. The note is at most 500 characters, like the other notes.
- **The command lives in `apps/emergencies`,** not `apps/core`, because it is about emergency cases. `seed_demo` is in `core` only because it spans every app.
- **`render.yaml` is unchanged.** The default of 30 applies on Render. Set `EMERGENCY_ESCALATION_MINUTES` in the Render dashboard to change it.
