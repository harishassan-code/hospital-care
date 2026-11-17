# Construction Plan: Emergency severity and priority

**Spec:** [docs/aidlc/inception/2026-11-17-emergency-severity-and-priority.md](../inception/2026-11-17-emergency-severity-and-priority.md)
**Date:** 2026-11-17

## Design

- `Severity` becomes `critical`, `high`, `moderate`, `low`, in priority order. `max_length` stays 10 (`moderate` is 8).
- **Migration `0003_severity_levels`:** an `AlterField` for the new choices, then a `RunPython` that maps
  `urgent` → `high` and `routine` → `moderate`. The reverse maps `high` → `urgent`, `moderate` → `routine` and
  `low` → `routine` (`low` has no older name, so it falls back to routine). Choices are not enforced by the
  database, so the data step can run with either set of choices in place.
- **Ordering:** `EmergencyRequest.objects` gets an `EmergencyRequestQuerySet` with `by_priority()`. It annotates a
  `Case/When` rank from the severity's position in `Severity` and orders by `(rank, created_at, id)`. It is portable
  (no DB-specific sort), and `id` breaks ties between cases opened in the same instant. The model's `Meta.ordering`
  stays as it is; only the list view uses `by_priority()`.
- **No client sort:** the Emergencies page renders the array in the server's order. The table caption says so.
- **Critical marker:** the critical row gets a tinted background and a `--stripe` left edge in `--status-critical`
  (the same pattern as the access-denied panel), and its severity cell is a `StatusBadge` tone `critical`, which
  has an octagon icon and the text "Critical". The other levels use the warning tone for high and the neutral tone for
  moderate and low, each with its own label. No new tokens or libraries.
- **Form:** the four levels, in the same order, with the same radio pattern as before. Each has a one-line hint.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend: `Severity` choices, migration `0003` (alter + data mapping with reverse), `by_priority()` used by the list view, API and ERD docs | `backend/apps/emergencies/{models,views,migrations/0003_severity_levels}.py`, `backend/apps/emergencies/tests/test_cases.py`, `backend/apps/emergencies/tests/test_severity.py`, `docs/architecture/api.md`, `docs/architecture/erd.md`, `docs/product/wireframes.md` | pytest: the migration's forward and reverse mapping runs against rows; list order is severity, then oldest first (ages set with explicit `created_at`); `urgent` → 400; each new level is accepted; the old list test is updated to the new order |
| 2 | Frontend: `Severity` type and `SEVERITIES`, critical row marker, labels, form CSS, fixture and mock severities, page caption | `frontend/src/api/emergencies.ts`, `frontend/src/features/emergencies/{Emergencies.module.css,NewCaseForm.tsx,emergencies.test.ts}`, `frontend/src/pages/staff/{EmergenciesPage.tsx,EmergenciesPage.test.tsx}`, `frontend/src/test/fixtures/emergencies.ts` | vitest: list renders in the server's order (no client sort); the critical row shows a "Critical" label and the others their own labels; the form offers the four levels |

## Sequencing

Unit 1 before unit 2: the frontend mocks follow the API's four values, which unit 1 makes real.

## Test plan

- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && pytest`
  on SQLite and on Postgres.
- Migrations forward and back on a fresh SQLite database: `migrate`, `migrate emergencies 0002`, `migrate`.
- `cd frontend && npm run lint && npm test && npm run build`
- Manual: sign in as `doctor@demo.citycare.pk`, open a critical and a low case, and check that the critical case is
  listed first with its "Critical" label and tinted edge.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Round trip is lossy for `low`:** migrating back turns `low` into `routine`, and forward again into `moderate`.
  Cases opened as `low` after this ships keep their level going forward; a rollback to 0002 cannot keep it.
- **The list is reloaded after opening a case**, instead of inserting the new case at the top. The server decides
  where it goes (severity, then age), so the page doesn't have its own ordering rule to keep in step.
- **Older records are left as they were:** the #30 inception and construction docs still say critical/urgent/routine,
  since they record decisions at the time. The public landing page's "Urgent" is a patient-facing triage category
  and is unchanged.
- Verified on SQLite (migrate, back to 0002, forward with rows at each level) and Postgres (full backend suite).
