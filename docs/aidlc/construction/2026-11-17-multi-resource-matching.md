# Construction Plan: Multi-resource matching

**Spec:** [docs/aidlc/inception/2026-11-17-multi-resource-matching.md](../inception/2026-11-17-multi-resource-matching.md)
**Date:** 2026-11-17
**Author:** Krrishna

## Design

- **Matching module.** `backend/apps/matching/multi.py` holds the pure step, with no queries:
  - `NeedMatch`: one short need as a hospital sees it: the `RequestItem`, its `shortfall`, and `available`, what the
    hospital has for it after the earlier needs of the same stock have claimed theirs.
  - `HospitalMatch`: `hospital`, `total_needs`, `covered` (needs fully covered), `unmet` (every other need, with
    `available` 0 when the hospital is not a candidate at all), `partial` (the unmet ones it has some of), `complete` (no
    unmet needs), `score` (the mean of its #41 scores, one decimal) and `distance_km` / `travel_minutes` from any of its
    candidates.
  - `match_hospitals(item_candidates)`: one `HospitalMatch` per hospital that is a candidate for at least one short need,
    in the order the spec gives. It calls `rank()` from #40 for the scores, so the scores are the same ones the per-need
    lists show.
- **Shared stock.** `availability._stock_key` gives each need its stock. For each hospital, the needs are walked in item
  order and a running count per key is kept, the same way `local_availability` does it for the case's own hospital.
  `_stock_key` also gets an operating-room branch: until now every operating-room line shared the key of a blank bed
  type, so two room lines with different capabilities were judged together. The local check never reads this key for
  operating rooms, so its behaviour does not change.
- **Endpoint.** `CaseCandidatesView` adds `hospitals: HospitalMatchSerializer(match_hospitals(found))`. The serializer is
  in `backend/apps/emergencies/serializers.py` beside `CandidateItemSerializer`. It reuses `need_label` for the labels.
  `candidates_for_case` does not change, and nothing new queries the database.
- **Frontend.** `frontend/src/api/emergencies.ts` gets `HospitalMatch` and the `hospitals` field on `CandidatesResponse`.
  `EmergencyCasePage.tsx`'s `Sources` panel shows a "Best single destination" section above the per-need lists when the
  response has two or more items. The distance text is shared with the per-need rows. The fixtures and mock API carry the
  new field.
- **Not changed.** `candidates.py`, the scoring rules, the feed, the blood app and the settings.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Docs: inception and this construction plan | `docs/aidlc/inception/2026-11-17-multi-resource-matching.md`, `docs/aidlc/construction/2026-11-17-multi-resource-matching.md` | none |
| 2 | Matching: the pure per-hospital judgement, shared stock, the order, `_stock_key` for operating rooms | `backend/apps/matching/multi.py`, `backend/apps/emergencies/availability.py` | `backend/apps/matching/tests/test_multi.py` |
| 3 | API: the `hospitals` field and its serializer | `backend/apps/emergencies/serializers.py`, `backend/apps/emergencies/views.py` | `backend/apps/emergencies/tests/test_candidates_api.py`, `backend/apps/matching/tests/test_candidates_performance.py` |
| 4 | Frontend: types, fixtures, mock API, the section and its styles | `frontend/src/api/emergencies.ts`, `frontend/src/test/fixtures/emergencies.ts`, `frontend/src/test/mockApi.ts`, `frontend/src/pages/staff/EmergencyCasePage.tsx`, `frontend/src/features/emergencies/Emergencies.module.css` | `frontend/src/pages/staff/EmergencyCasePage.test.tsx` |
| 5 | API doc: the `hospitals` field and the ordering rule | `docs/architecture/api.md` | none |

## Sequencing

Unit 1 first, as the spec requires. Unit 2 next, since the API and the screen both use it. Unit 3 after unit 2, and
unit 4 once the API shape is fixed. Unit 5 last.

## Test plan

Backend, `test_multi.py`:

- A hospital with every need ranks above one with a better score that is missing a need.
- Among partial hospitals, the one that covers more ranks higher.
- `unmet` lists exactly the missing needs, with their missing counts.
- A partial quantity is unmet, with `available` set to what the hospital has.
- Shared stock: two O− red-cell lines at a hospital with stock for one are not both covered, and the first line gets it.
- Operating-room lines with different capabilities are not judged as one stock.
- Ties are ordered by distance, then by hospital id, every time.
- `recommended` only when complete (in the API tests).
- An empty list when nothing is short.

Backend, API and query budget:

- The shape of `hospitals`, with `rank`, `complete`, `recommended`, `coverage`, `covered` and `unmet`.
- The end-to-end case: ICU bed, ventilator and blood across three hospitals, where only one has all three.
- The candidates pipeline with `match_hospitals` and its serializer makes the same number of queries as without them.

Frontend, `EmergencyCasePage.test.tsx`:

- The section renders in server order, with "Has everything" and "Recommended" as text.
- Partial hospitals list what they are missing, with "only N of M" for partial quantities.
- The "No single hospital has everything" line appears when no hospital is complete.
- The section is hidden with one short need.

Verification, from the task: Postgres and SQLite pytest, ruff check and format, `makemigrations --check`, `manage.py check`,
frontend lint, test and build, and a grep for the writing rules.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Found while building.** `_stock_key` gave every operating-room line the key of a blank bed type, so two room lines
  with different capabilities would have been judged as one stock. It now keys an operating room by its capability. The
  local check (#33) handles rooms by id and never read this key for them, so its behaviour is unchanged. A test covers
  the cardiac and general case.
- **Verified.** Postgres: 921 passed. SQLite: 918 passed, 2 skipped, and one failure that is not this story's
  (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, the known SQLite issue). Ruff check and format
  are clean, `makemigrations --check` detects no changes, and `manage.py check` reports no issues. Frontend: lint clean,
  380 tests in 38 files passing, production build passing.
- **Query budget.** The `hospitals` field is worked out from the candidates already fetched, and its serialising reuses
  the item labels. `test_candidates_performance.py` asserts that the search with `hospitals` makes the same number of
  queries as the search without it, within the #38 budget of 10.
- **Not done here.** Nothing is reserved or allocated at the matching hospital (#45). The two known limits in the spec
  (blood donors across groups, operating rooms with two capabilities) are documented in `docs/architecture/api.md` and
  are not solved.
- The inception doc's sign-off is pending the Product Owner.
