# Construction Plan: Find candidate hospitals

**Spec:** [docs/aidlc/inception/2026-11-17-find-candidate-hospitals.md](../inception/2026-11-17-find-candidate-hospitals.md)
**Date:** 2026-11-17
**Author:** Krrishna

## Design

- **Requirement types (#32, completed).** `ResourceType` gains `equipment` and `operatingRoom`. `RequestItem` gains two
  fields: `equipment_type` (choices from `EquipmentType`) and `capability` (choices from `OrCapability`). Only the field of
  a need's own type is set. Migration `0005`. The API names are `equipmentType` and `capability`.
  - `RequestItemSerializer` validates per type: blood needs `group` and `component`, bed needs `bedType`, equipment needs
    `equipmentType`, operating room needs `capability`. Quantity limits: equipment 5 and operating rooms 3 per line.
  - `create_case` stores only the fields of the need's type. Other fields are stored blank.
- **Local availability (#33, extended).** `backend/apps/emergencies/availability.py`:
  - Equipment: one grouped count of `Equipment.objects.matchable()` at the case's hospital, by type. Its key is
    `("equipment", type)` and it uses the same shared-stock rule as blood and beds.
  - Operating rooms: one query for the hospital's matchable rooms with their capability lists. A room is a single stock
    unit, so it is claimed once: a line takes the lowest-id unclaimed rooms with its capability, and later lines see what is
    left. This stops a cardiac-and-general room from covering both a cardiac line and a general line. Greedy in list order:
    it can overstate a shortfall when a multi-capability room is claimed by a line that had another room to take, and it
    never understates one.
  - The detail costs one query per resource type (four stock queries) plus the case, its needs, its history and the
    overdue check: 8 queries whatever the number of needs.
- **Candidate search.** `backend/apps/matching/candidates.py`:
  - `REGISTRY` maps each `ResourceType` to a function returning the matchable resources for one requirement, as a queryset
    of a `Resource` subclass:
    - blood: `compatible_units(group, component)` (#37), with usable units only and `donor_rank`;
    - bed: `Bed` with status free and the type;
    - equipment: `Equipment.objects.matchable()` of the type;
    - operating room: `OperatingRoom.objects.matchable().with_capability(code)`.
  - `_grouped(item, origin_id)` is the generic part. It drops the origin hospital and inactive hospitals, then runs one
    `values("hospital_id").annotate(...)`: `Count` for every type, plus `Min(expires_at)` and `Min(donor_rank)` for blood.
    Its ordering is cleared first, so `compatible_units`' order does not leak into the group by.
  - `find_candidates(item, *, origin_hospital, needed) -> list[Candidate]` runs the grouped query and one `in_bulk` for the
    hospitals it lists.
  - `candidates_for_case(case) -> list[ItemCandidates]` runs `shortfall_items(case)`, then one grouped query per short
    item, then a single `in_bulk` for the hospitals of all items together. It does not query per hospital.
  - `Candidate` is a dataclass: `hospital` (a `Hospital`), `available`, `covers`, `distance_km`, `travel_minutes` (rounded
    from #39's `estimated_travel_minutes`, which is called without a speed), `earliest_expiry` and `best_donor_rank` (blood
    only; None otherwise).
  - Distance is None when the origin is None or either hospital lacks coordinates. The model requires coordinates, so that
    case is checked by a unit test on unsaved instances.
  - Order: covers first, then distance (None last), then hospital id.
- **Per-requirement counts.** Each requirement counts the network's stock on its own. Two lines can both count one remote
  unit. Allocation (#45) claims stock. This is recorded in the inception spec as an open question.
- **API:** `GET /api/emergencies/<reference>/candidates/` in `backend/apps/emergencies/views.py`
  (`CaseCandidatesView`). It uses the same `own_hospital` read rule as the detail, so another hospital's case is 404 and a
  patient gets 403. It does not call `escalate_overdue`. The response is `{reference, items}`, where `items` holds one entry
  per short requirement and is empty when nothing is short. Each candidate carries `hospital`, `available`, `covers`,
  `distanceKm` (1 decimal or null), `travelMinutes` (int or null), and for blood `earliestExpiry` and `bestDonorRank`.
  Serializer: `CandidateItemSerializer` in `backend/apps/emergencies/serializers.py`.
- **Frontend:** the case page fetches the candidates in a child panel, only when the case has a shortfall. The panel is
  "Sources in the network". Each short requirement lists its candidates with the available count, a "covers it" or "partial"
  marker, the distance and travel time ("4.2 km · ~6 min"), and the earliest expiry for blood. A requirement with none reads
  "No other hospital has this right now". The page renders the server's figures and does not compute them. Labels for the new
  types are in `features/emergencies/emergencies.ts`.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Requirement types: model fields, migration `0005`, serializer validation per type, `create_case` storage, feed accepts the types, docs | `backend/apps/emergencies/{models.py,serializers.py,services.py,migrations/0005_*.py}`, `docs/architecture/api.md` | create validation per type; stored fields blank for other types; a blood or bed need unchanged |
| 2 | Local availability for equipment and operating rooms, room claims, query count | `backend/apps/emergencies/availability.py`, `backend/apps/emergencies/tests/test_availability.py` | matchable equipment of the type only; available rooms with the capability only; a multi-capability room claimed once; shortfall for the new types |
| 3 | Candidate search: registry, generic grouped query, `Candidate`, `find_candidates`, `candidates_for_case` | `backend/apps/matching/candidates.py`, `backend/apps/matching/tests/test_candidates.py` | per-type counts; origin and inactive hospitals excluded; zero-stock omitted; covers; order; distance and travel present, None without coordinates or origin; blood expiry and rank; query budget flat as the network grows |
| 4 | API endpoint, serializer, URL, API docs | `backend/apps/emergencies/{views.py,serializers.py,urls.py}`, `backend/apps/emergencies/tests/test_candidates_api.py`, `docs/architecture/api.md` | shape; 404 for another hospital's case; 403 for a patient; items omitted when covered locally; empty list when nothing is short |
| 5 | Performance: seeded network, one need of each type | `backend/apps/matching/tests/test_candidates_performance.py` | under 1 second and within a fixed query budget on `seed_demo` data |
| 6 | Frontend: types, labels, form, case page sources panel, mock API and fixtures | `frontend/src/api/emergencies.ts`, `frontend/src/features/emergencies/{emergencies.ts,NewCaseForm.tsx,emergencies.test.ts}`, `frontend/src/pages/staff/{EmergencyCasePage.tsx,EmergencyCasePage.test.tsx,EmergenciesPage.test.tsx}`, `frontend/src/test/{mockApi.ts,fixtures/emergencies.ts}` | the new types in the form and the case page; the sources panel with both markers and the empty state; the request and error mapping |

## Sequencing

Unit 1 before 2, 2 before 3 (the candidates use `shortfall_items`), 3 before 4, and 4 before 6 (the mock follows the real
response). Unit 5 after 3 and 4, since it measures the finished search.

## Test plan

- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run` and `pytest`
  on SQLite and on Postgres.
- Migrations forward, back and forward on SQLite.
- `cd frontend && npm run lint && npm test && npm run build`.
- Timing: the endpoint, once on Postgres with `seed_demo` data (recorded below).

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified.** Postgres: 851 passed. SQLite: 848 passed, 2 skipped, and one failure that is not this story's
  (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, the known SQLite issue). Ruff check and format,
  `makemigrations --check` and `manage.py check` are clean. Migration `0005` runs forward, back and forward on SQLite.
  Frontend: lint clean, 370 tests pass, the build succeeds.
- **Timing (acceptance).** `GET /api/emergencies/<ref>/candidates/` on Postgres, against `seed_demo` data: one need of each
  type at Seaview Hospital (50 units of A+ red cells, 50 general beds, 50 ventilators, 50 general operating rooms). One
  request: HTTP 200 in **10.1 ms**, **11 queries** in all (the case, its needs, four stock counts, one grouped search per
  short need, one hospital fetch). The pytest performance test asserts `candidates_for_case` under one second and within a
  budget of 10 queries on the same data.
- **Query budget is flat.** A test grows the network from two stocked hospitals to fourteen, with twelve more holding beds
  only, and asserts the same count for a four-need case. The count does not depend on hospitals or resources.
- **Seeded network.** No ICU bed is free at any hospital other than the origin, and the cardiac theatre is in use at every
  hospital, so the timing case asks for general beds and a general operating room. A cardiac need at seeded hospitals returns no
  candidates, which is correct.
- **Room claims.** A room with two capabilities is one unit of stock, so a cardiac line and a general line that both want it
  leave one short. The claim is greedy in list order and takes the lowest id first. It can overstate a shortfall when a
  multi-capability room is taken by a line that had another room to take. It never understates one.
- **Stray fields.** The spec asked that fields of other types be blank. They are stored blank. A need that also sends a field
  of another type has that field ignored, as blood and bed needs already did (an existing test pins this), rather than
  rejected.
- **Feed.** `GET /emergencies/feed/` accepts `equipment` and `operatingRoom` now, because the type list is the resource
  type list. The feed page itself still shows blood and beds.
- **Frontend.** The sources panel is fetched only when the case has a shortfall, so a case covered locally makes no extra
  request. A select's error is announced with it (`aria-describedby`), as a text field's already was.
- **Not done here:** candidates are not ranked or scored (#40, #41), nothing is reserved or requested from another hospital
  (#45), and no commit or push. The inception doc's sign-off is pending the Product Owner.
