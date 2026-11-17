# Construction Plan: Local availability check

**Spec:** [docs/aidlc/inception/2026-11-17-local-availability-check.md](../inception/2026-11-17-local-availability-check.md)
**Date:** 2026-11-17

## Design

- **One module:** `backend/apps/emergencies/availability.py`, with no model or migration changes.
  - `ItemAvailability` is a dataclass: `item` (the `RequestItem`), `available` (int), `shortfall` (int).
  - `local_availability(case) -> list[ItemAvailability]` returns one row per item, in the order of `case.items.all()`.
    It runs one aggregated query per resource type, not one per item:
    - blood: a grouped count of usable units at the case's hospital by `(group, component)`;
    - beds: a grouped count of free beds at the case's hospital by `bed_type`.
    A case with no hospital gets 0 for every item and runs no query.
  - `shortfall_items(case) -> list[tuple[RequestItem, int]]` returns only the items with a shortfall above 0. Its docstring
    says the matching step (#38) is its caller.
- **Usable units:** the blood app already defined "usable" inline in `stock_summary` (status `available`, `expires_at` after
  now). It is now `usable_units(units, now=None)` in `apps/blood/services.py`, and `stock_summary` calls it. The
  availability module uses the same helper, so the two cannot drift.
- **Shortfall:** `max(0, item.quantity - item.fulfilled - available)`.
- **API:** `CaseDetailSerializer` is the only serializer that changes. Its `to_representation` calls `local_availability`
  once, then adds `localAvailable` and `shortfall` to each item and `shortfallTotal` (the sum of the shortfalls) to the case.
  The list serializer and the list view are untouched.
- **Query count:** the detail costs a fixed number of queries whatever the number of items: the case, its items, its
  history, and the two grouped counts. The test pins the bound.
- **Frontend:** the case page's needs list shows, for each requirement, the need, "Available here: N" and either
  "Short: M" or "Covered locally". Each is text. The summary line under the list is "Everything is available here" or the
  count of units and beds needed from other hospitals. The page renders the server's figures and does not recompute them.
  The mock API derives the same figures from per-case local stock in the fixtures.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend: `usable_units` helper, `availability.py` (`local_availability`, `shortfall_items`), detail serializer fields, API docs | `backend/apps/blood/services.py`, `backend/apps/emergencies/availability.py`, `backend/apps/emergencies/serializers.py`, `backend/apps/emergencies/tests/test_availability.py`, `docs/architecture/api.md` | pytest: blood counts only the exact group, component, hospital, status and unexpired units; beds count only free beds of the type at the hospital; shortfall subtracts fulfilled and never goes negative; `shortfall_items` returns only short items; a case without a hospital has 0; the detail has the fields and the list does not; the detail's query count is bounded |
| 2 | Frontend: API types, case page availability and summary, mock API and fixtures | `frontend/src/api/emergencies.ts`, `frontend/src/features/emergencies/{emergencies.ts,emergencies.test.ts,Emergencies.module.css}`, `frontend/src/pages/staff/EmergencyCasePage.tsx` (+ `.test.tsx`), `frontend/src/test/mockApi.ts`, `frontend/src/test/fixtures/emergencies.ts` | vitest: each item shows "Available here" and "Short" (or "Covered locally"); the summary reads "Everything is available here" when nothing is short and the count when something is |

## Sequencing

Unit 1 before unit 2: the frontend types and the mock follow the API fields that unit 1 makes real.

## Test plan

- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && pytest`
  on SQLite and on Postgres.
- `cd frontend && npm run lint && npm test && npm run build`
- Manual: sign in as `doctor@demo.citycare.pk`, open a case, and check that each need shows its local figures and the summary.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified:** SQLite, full suite: 327 passed and one failure that is not this story's (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, a known SQLite issue). Postgres: 328 passed. Ruff check and format, and `makemigrations --check`, clean. Frontend: lint clean, 290 tests pass, build succeeds.
- **Shared stock is drawn down in list order.** The first design gave every need the full local stock, so two lines for O- red cells (3 each, 4 in stock) both showed 4 available and 0 short. The total would have been wrong. Needs that use the same stock now share it in list order, and the spec's shortfall formula applies to each row as written.
- **The query count is pinned at 5** for a case with a hospital and items: the case, its needs, its history, and one grouped count each for blood and beds. A test checks that a case with one need and a case with five take the same number of queries.
- **Usable units come from one helper.** `usable_units()` in `apps/blood/services.py` now backs both `stock_summary` and the local count. The blood list view still inlines the same status and expiry filter; it was left alone to keep this change small.
- **Singular wording.** The summary reads "1 unit or bed needed from other hospitals" for a total of 1, where the spec's template would read "1 units/beds". Plural totals follow the template.
- **Mock data.** The mock API's local figures come from `sampleLocalAvailable` in the fixtures. It does not re-derive them from stock, and it ignores `fulfilled`, which the API does not send.
- **Not done here:** no commit, no push. The inception doc's sign-off is pending the Product Owner.
