# Construction Plan: Atomic resource reservation

**Spec:** [docs/aidlc/inception/2026-11-17-atomic-resource-reservation.md](../inception/2026-11-17-atomic-resource-reservation.md)
**Author:** Krrishna
**Date:** 2026-11-17

## Design

- **Model:** `Reservation` in `apps/matching/models.py`, as the ERD's Reservation with the fields the spec adds
  (hospital, reserved_by, created_at, ended_at, end_reason). The resource is a `GenericForeignKey` (content type and
  object id). Its constraints:
  - A partial `UniqueConstraint` on `(content_type, object_id)` where `status` is `held` or `allocated`. This is the
    database guarantee that one resource has one active hold.
  - An index on `(status, expires_at)` for the expiry sweep.
  - No `fulfilled >= 0` constraint is added: `PositiveSmallIntegerField` already gives `CHECK (fulfilled >= 0)` on both
    databases (confirmed from Django's SQLite and Postgres backends). It is tested instead.
- **Settings:** `RESERVATION_HOLD_MINUTES = positive_int_env("RESERVATION_HOLD_MINUTES", 30)`, next to the escalation
  setting. Documented in `backend/.env.example` and `docs/setup/deployment.md`.
- **Service:** `apps/matching/reservations.py`:
  - `reserve(item, *, hospital, quantity, actor) -> list[Reservation]`. In `transaction.atomic()`: lock the case
    (`select_for_update`), lock the need, then count its active holds and clamp against the quantity, then take up to
    `quantity` resources from the registry querysets at `hospital`, locked with `select_for_update(skip_locked=True)`.
    The registry queryset also excludes any resource with an active hold. Each resource moves through
    `change_status(resource, "reserve")`, and a `Reservation` is created with `expires_at = now + RESERVATION_HOLD_MINUTES`.
    An open case moves to matching through the lifecycle (system move). Audit: `reservation.created`.
  - `release(reservation, *, actor, reason)`: lock the hold, then its resource. The resource moves through
    `cancelReservation` when its status still allows it. A hold that is not `held` raises `ReservationNotHeld`.
  - `release_expired(now=None) -> int`: the sweep. Candidates are `held` rows past `expires_at`, each locked with
    `skip_locked`, then re-checked under the lock. Idempotent, because an expired hold is no longer `held`.
  - `ReservationUnavailable` (nothing free, or the need has no room left) and `ReservationNotHeld` are plain exceptions.
    Views map them to 400 and 409.
- **Local availability:** `local_availability` counts each need's active holds (held and allocated) in one query and
  subtracts them from the need, so a case's own held stock is not requested from other hospitals. The detail's query count goes
  from 8 to 11 (see the notes below).
- **Case move:** the status move is extracted from `apps/emergencies/services.py`. `_move` becomes `move_case` (public),
  so `apps.matching` can use it. Its three callers change with it.
- **Triggers:** `release_expired()` runs at the start of the candidates GET, the case detail GET and the two reservation
  endpoints (`ponytail:` request-time sweep, the same as escalation). The management command
  `release_expired_reservations` (in `apps/matching/management/commands/`) prints the count.
- **API:** `POST /api/emergencies/<ref>/reservations/` and `POST .../reservations/<id>/release/`, with the case detail
  gaining `reservations` and a per-need `reserved` count. Permission: `module_permission("emergencies")`, with the case
  looked up under `own_hospital` (404 otherwise).
- **Lifecycles:** equipment and operating rooms gain `reserved` (choices plus `AlterField` migrations). Their
  `matchable()` still returns only `available`, so reserved items drop out of searches with no filter change.
- **Frontend:** the case page gets a per-need "Reserve N here" control (quantity defaults to the smaller of the local
  available and the remaining need) and a "Reservations" list with a release button. Errors show in `FormAlert`. The
  equipment and operating-room lifecycle tables and their labels mirror the backend moves.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend: `Reservation` model, its constraints, `matching` migration; `reserved` status on equipment and operating rooms with their migrations and lifecycle moves | `backend/apps/matching/models.py`, `backend/apps/matching/migrations/0001_initial.py`, `backend/apps/equipment/{models.py,migrations/0002_equipment_reserved_status.py}`, `backend/apps/operating_rooms/{models.py,migrations/0003_room_reserved_status.py}` | `backend/apps/matching/tests/test_reservation_constraints.py` (second active hold refused, released-then-held allowed, fulfilled bounds, negative fulfilled); lifecycle moves in `backend/apps/equipment/tests/` and `backend/apps/operating_rooms/tests/` |
| 2 | Backend: the reservation service (`reserve`, `release`, `release_expired`), `move_case`, the setting, the command | `backend/apps/matching/reservations.py`, `backend/apps/emergencies/services.py`, `backend/config/settings.py`, `backend/apps/matching/management/commands/{__init__,release_expired_reservations}.py`, `backend/apps/matching/tests/reservation_support.py` | `backend/apps/matching/tests/test_reservations.py` (picks by rank then expiry, status moves, expires_at, case to matching, audit, partial, none, over-quantity, remaining guard, closed case refused); `backend/apps/matching/tests/test_reservation_release.py` (release, expiry, idempotence, hold setting, command); reserved resources absent from availability, candidates, compatible units, matchable() |
| 3 | Backend: API, case detail `reservations` and `reserved`, shortfall net of holds, triggers on the GETs | `backend/apps/emergencies/{availability,serializers,views,case_urls}.py`, `backend/apps/emergencies/tests/{test_reservations_api,test_availability}.py` | `backend/apps/emergencies/tests/test_reservations_api.py` (shape, own-hospital 404, 403 for roles without edit, release 409, reserve 400s, triggers) and the query-count pins |
| 4 | Backend: concurrency tests on Postgres (#44) | `backend/apps/matching/tests/test_reservation_concurrency.py` | 8 threads, one unit: exactly one succeeds; 8 threads, 3 units: exactly 3 succeed; run 5 times |
| 5 | Frontend: API types and calls, lifecycle tables and labels for equipment and rooms, the case page's reserve and release controls, mock API | `frontend/src/api/{emergencies,equipment,operatingRooms}.ts`, `frontend/src/features/equipment/equipment.ts`, `frontend/src/features/operatingRooms/operatingRooms.ts`, `frontend/src/features/emergencies/Emergencies.module.css`, `frontend/src/pages/staff/{EmergencyCasePage,EquipmentPage,OperatingRoomsPage}.tsx` (+ tests), `frontend/src/test/mockApi.ts` | vitest: reserve sends the right body and shows the list; a 400 shows in `FormAlert`; release sends the request; the default quantity; the moves for reserved equipment and rooms |
| 6 | Docs | `docs/architecture/{api.md,erd.md,resources.md}`, `docs/setup/deployment.md`, `backend/.env.example`, these two AIDLC files | none (reviewed with the PR) |

## Sequencing

Unit 1 before 2, since the service uses the model. Unit 2 before 3, since the API calls the service. Unit 4 needs
units 1 and 2. Unit 5 follows unit 3, because the frontend types follow the API. Unit 6 is last, so the docs describe
what was built.

## Test plan

- `cd backend && $V/python -m pytest -q -p no:cacheprovider` on SQLite. One known failure:
  `apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`.
- The same on Postgres, through the local wrapper. The concurrency tests must run there, not skip.
- `ruff check .`, `ruff format --check .`, `makemigrations --check --dry-run`, `DJANGO_DEBUG=true manage.py check`.
- Migrations forward, back and forward on SQLite; `migrate` and `seed_demo` on Postgres.
- `cd frontend && npm run lint && npm test && npm run build`.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.

## Notes from construction (2026-11-17)

- **Verified.** SQLite, full suite: 1038 passed, 5 skipped (the three concurrency tests, which need PostgreSQL, and two
  existing PostgreSQL-only tests), and one failure that is not this story's: `apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`,
  the known SQLite issue. PostgreSQL, full suite: 1044 passed, nothing skipped. Ruff check and format, `makemigrations --check` and
  `manage.py check` are clean. Migrations went forward, back and forward on SQLite. `migrate` and `seed_demo` (run twice) work on
  PostgreSQL. Frontend: lint clean, 386 tests pass (380 before this story), build succeeds.
- **Concurrency (#44).** Five runs of the concurrency file on PostgreSQL: three tests passed each time. Eight threads fire at one
  unit from eight cases, and exactly one succeeds. Eight threads fire from one case and need, and exactly one succeeds. Eight
  threads fire at three units, and exactly three succeed. To check that the tests can fail, the `skip_locked` lock was removed
  once: the two multi-case tests then failed, with the partial unique index refusing the second hold (`IntegrityError`).
  The lock was restored. The one-case variant still passes without the lock, because the case row lock serializes it.
- **The fulfilled check.** `fulfilled >= 0` is not added as a constraint. Django's `PositiveSmallIntegerField` already creates
  it on both databases, and a test shows SQLite refusing a negative value.
- **Shortfall nets the holds.** The spec did not say to change `local_availability`, but a case that holds its own stock would
  otherwise ask other hospitals for it. The shortfall now subtracts the need's holds (held and allocated). The query count of
  the detail went from 8 to 11: the annotated items query, the request-time expiry check, and the holds query. The pin's comment
  says why.
- **Blood at the case's own hospital can be a compatible group,** exact groups first, because `reserve` uses the registry (open
  question 1). The "Available here" count stays exact-only, as #33 has it.
- **`_move` is now `move_case`,** so `apps.matching` can call it. Same behaviour, three call sites.
- **Detail items carry `itemId`.** The reserve endpoint needs the need's id, and the detail had none. The candidates list already
  used `itemId`, so the two now agree.
- **The page's reserve form is `noValidate`,** so the page's own message ("Enter a whole number from 1 to 4.") is the one shown,
  rather than the browser's.
- **Not done, and open.** Manual `reserve` and `cancelReservation` through the action endpoints (equipment, rooms, and the
  existing blood and bed endpoints) can leave a hold row out of step with its resource (open question 2). A reserved bed still
  has no way to become occupied (open question 3, for #45).
