# Construction Plan: Allocation record and blood allocation

**Spec:** [docs/aidlc/inception/2026-11-17-allocation-record-and-blood-allocation.md](../inception/2026-11-17-allocation-record-and-blood-allocation.md)
**Author:** Krrishna
**Date:** 2026-11-17

## Design

- **Model:** `Allocation` in `apps/matching/models.py`, per the ERD:
  - `reservation`: one-to-one to `Reservation` (`PROTECT`, `related_name="allocation"`). One allocation per hold.
  - `request` (`emergencies.EmergencyRequest`, `PROTECT`, `related_name="allocations"`), `request_item`
    (`emergencies.RequestItem`, `PROTECT`), `hospital` (the supplier, `PROTECT`).
  - `content_type` and `object_id`, copied from the reservation, so the record names the resource even if the resource
    later moves on. `allocated_by` (user, `PROTECT`), `at` (default now) and `note` (blank).
  - No update or delete endpoints. The admin is read-only.
- **Service:** `apps/matching/allocations.py`.
  - `allocate(reservation_id, *, actor, note="") -> Allocation`, in `transaction.atomic`. Locks in the same order as
    reservations: case, need, hold, then resource (`select_for_update`). Then, in order:
    1. Refuse unless the hold is `held` and `expires_at` is in the future (`ReservationNotHeld`, 409).
    2. Refuse unless the case can take stock (`RESERVABLE` from `reservations.py` without the fulfilled case; 409).
    3. Permission: module edit for the need's type, and `may_change` on the resource (`PermissionDenied`, 403).
    4. Move the resource with `change_status(..., held_ok=True)`: `issue`, `admit`, `use` or `startCase`. A bed also gets
       `admitted_at = now`.
    5. Hold to `allocated`, with `ended_at` and `end_reason`.
    6. Need `fulfilled += 1`. The `CheckConstraint` backs it up.
    7. Create the `Allocation` and audit it (`allocation.created`).
    8. Recompute the case through `move_case` (the module-level name, so tests can patch it) as a system move: start
       matching or resume matching first when needed, then `fulfil` when every need is full, or `partiallyFulfil`. A
       partially fulfilled case that stays partial makes no move.
  - `allocate_many(reservation_ids, *, actor) -> list[Allocation]`. One transaction over `allocate`. Holds are taken in
    case-id order, so two batches lock cases in the same order.
- **Shared rule change:** a need's open count is `quantity - fulfilled - held`, counting `held` only. Allocated holds
  are already in `fulfilled`. `active_holds` (in `reservations.py`) and the `active` annotation in
  `local_availability` count held only. `_free_resources` still excludes any resource with an `ACTIVE` hold, so a
  resource can't be held twice.
- **Bed lifecycle:** `(RESERVED, "admit") -> OCCUPIED` in `BED_LIFECYCLE`. The bed action endpoint takes `admit`, and
  it sets `admitted_at` when the bed is admitted. Patient fields stay blank. A bed with an active hold is refused by
  `change_status`, so the action can't skip allocation.
- **Case list shape:** `EmergencyRequest` severity ordering moves into `severity_rank()` in `emergencies/models.py`. `by_priority`
  and the held-reservations list both use it.
- **API:**
  - `apps/matching/urls.py`, mounted at `/api/reservations/`:
    - `GET ""`: held reservations at the user's hospital (admins: all), for the types the user may see. Query `type`,
      optional. Ordered by severity, case age, expiry, then id. Each entry carries `canAllocate`.
    - `POST <id>/allocate/`: 201 with the `Allocation`.
    - `POST allocate/` with `{ids}`: 201 with the list, all or nothing.
    - Views in `apps/matching/views.py`. Each calls `release_expired()` first. A hold at another hospital the user can't
      see is 404 (`own_hospital` on the reservation queryset).
  - Case detail: `allocations` (oldest first), per-need `fulfilled` and `remaining`, and `canAllocate` on each
    reservation. The detail and action views pass the user in the serializer context.
- **Frontend:** the case page and the Blood page as the spec describes. Types, mocks and fixtures follow the API.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Backend model: `Allocation`, `matching` migration, `severity_rank`, bed `admit` move, the held-only open count, admin read-only | `backend/apps/matching/{models.py,admin.py,migrations/0002_allocation.py}`, `backend/apps/emergencies/models.py`, `backend/apps/hospitals/models.py`, `backend/apps/matching/reservations.py`, `backend/apps/emergencies/availability.py` | `backend/apps/resources/tests/test_state_machine.py` (admit); `backend/apps/matching/tests/test_allocation_model.py` (constraints, admin read-only, PROTECT) |
| 2 | Backend service: `allocate`, `allocate_many`, the case recompute, bed `admitted_at` | `backend/apps/matching/allocations.py`, `backend/apps/hospitals/services.py` | `backend/apps/matching/tests/test_allocations.py` |
| 3 | Backend API: the reservations module, case detail changes, `canAllocate` | `backend/apps/matching/{urls.py,views.py,serializers.py}`, `backend/config/urls.py`, `backend/apps/emergencies/{serializers.py,views.py}` | `backend/apps/matching/tests/test_allocation_api.py`, `backend/apps/emergencies/tests/test_allocation_detail.py` |
| 4 | Frontend API and types, mock API, fixtures, bed lifecycle table | `frontend/src/api/{emergencies,blood,beds}.ts`, `frontend/src/test/{mockApi.ts,fixtures/*}`, `frontend/src/features/beds/beds.ts` | vitest: beds lifecycle includes admit |
| 5 | Frontend: case page Allocate, remaining and timeline; Blood page "Reserved for cases" | `frontend/src/pages/staff/{EmergencyCasePage,BloodPage}.tsx`, `frontend/src/features/emergencies/*`, `frontend/src/features/blood/*` | vitest: case page allocate flow; Blood panel lists, allocates single and all with confirm; view-only roles have no buttons |
| 6 | Docs | `docs/architecture/{api.md,erd.md,resources.md}`, these two AIDLC files | none (reviewed with the PR) |

## Sequencing

Unit 1 before 2 (the service uses the model). Unit 2 before 3 (the API calls the service). Unit 4 follows unit 3, since the
types follow the API. Unit 5 follows unit 4. Unit 6 is last, so the docs describe what was built.

## Test plan

- Backend, parametrized over the four types: `allocate` moves the resource to its final state, the hold becomes
  allocated, the `Allocation` links request, need, resource, hospital and actor, `fulfilled` rises, and an audit record
  is written.
- Case status: first allocation to partially fulfilled, last to fulfilled, escalated through resume matching, closed or
  cancelled refused (409), and the history entries are system moves.
- One transaction: `move_case` raises after the resource move. Nothing changes: the unit is still reserved, the hold is
  still held, `fulfilled` is unchanged, and there is no `Allocation`.
- Expired hold, released hold and a second allocation of the same hold: 409.
- Permissions: a blood bank user allocates blood but not a bed (403); a nurse allocates a bed; another hospital's hold is
  404 for a non-admin; an admin allocates at any hospital.
- `allocate_many` is all-or-nothing.
- The allocation is permanent: no endpoint changes it, and the admin is read-only.
- The held list: scoping, ordering, remaining and `canAllocate`.
- Case detail: `allocations` and `remaining`. Bed admitted from reserved.
- Frontend: the case page's Allocate flow updates the status and remaining, and the timeline shows the allocation. The Blood
  panel lists, allocates a unit, and allocates all for a need, each behind `window.confirm`. View-only roles see no
  Allocate buttons.
- Commands, run from `backend` and `frontend` as in the story's verification list: pytest on Postgres (through the wrapper)
  and SQLite, ruff check and format, `makemigrations --check`, `manage.py check`, migrations forward, back and forward on
  SQLite, `migrate` and `seed_demo` on Postgres, and `npm run lint`, `npm test`, `npm run build`.

## Review

Each unit is reviewed in the developer's weekly PR and again at the weekly integration PR, per
[CONTRIBUTING.md](../../../CONTRIBUTING.md). Those approvals are the Construction gate.
