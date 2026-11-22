# Construction Plan: Ambulance dispatch and trip tracking

**Spec:** [docs/aidlc/inception/2026-11-18-ambulance-dispatch.md](../inception/2026-11-18-ambulance-dispatch.md)
**Date:** 2026-11-18

B05 is one trip per transfer, carried by one ambulance. It builds on the transfer lifecycle (B01 to B03) and the ambulance
registry (B04). Its rules are in `apps/ambulances`; the transfer service only gains a guard and a way to be moved by a trip.

## Design

### Changes to the B04 ambulance app (`backend/apps/ambulances/`)

- `AmbulanceStatus` gains `dispatched` ("On trip"). `AMBULANCE_LIFECYCLE` gains `dispatch` (available → dispatched) and
  `release` (dispatched → available). `TRIP_ONLY_ACTIONS = ("dispatch", "release")` are refused by the manual endpoint (409).
- `Trip` (`models.py`): `transfer` (FK `transfers.Transfer`, PROTECT, `related_name="trips"`), `ambulance` (FK, PROTECT,
  `related_name="trips"`), `status` (`dispatched`, `enRoute`, `arrived`, `completed`), `eta_minutes` (set at dispatch),
  `dispatched_by`, `dispatched_at`, `departed_at`, `arrived_at`, `completed_at`. `TRIP_ACTIVE` = dispatched, en route,
  arrived. Two partial unique constraints, as `Reservation` does: one active trip per transfer and per ambulance.
- `TRIP_LIFECYCLE` (`StateMachine`): depart, arrive, complete.
- `services.py`: `may_dispatch_trip`, `may_step_trip` (edit on `ambulances` at the supplying hospital, admins any),
  `visible_ambulances`, `trip_eta_minutes`, `dispatch_trip`, `step_trip`, `trip_actions_for`. Every write is
  `transaction.atomic()`, locks transfer → ambulance (dispatch) or transfer → trip → ambulance (complete), and audit-logs
  through `record`.
- `serializers.py`: `TripSerializer` (the shape in `frontend/src/api/trips.ts`); `AmbulanceSerializer` gains `trip`
  (the active trip or null).
- `views.py` and `trip_urls.py`: `TransferTripView` (`POST /api/transfers/<id>/trips/`, mounted from
  `apps/transfers/urls.py`) and `TripActionView` (`POST /api/trips/<id>/actions/`, mounted in `config/urls.py`). The list
  takes `hospital=<id>` and `status=`.

### Changes to `apps/transfers` (minimal)

- `_lock` becomes the public `lock_transfer` (case → need → transfer), so the trip services can lock in the same order.
- `_begin` (every manual move) refuses with 409 while a trip is active, with a message to use the trip. Trip-driven moves
  pass `via_trip=True`: they skip the manual permission (the trip's own check applies) but keep the lifecycle.
- `dispatch` and `start_transit` take `via_trip`.
- `cancel_for_case` refuses (409, through the case view's existing `TransitionNotAllowed` handler) while a trip is
  active, so a closed case can't leave an ambulance on the road with its transfer cancelled.
- `actions_for` drops the manual moves while a trip is active. `TransferSerializer` gains `trip` (latest trip),
  `etaMinutes` (the route estimate) and `dispatchAmbulance` in `actions` (approved, and the user may dispatch).
- `with_details` prefetches the trips.

### Frontend

- `src/api/trips.ts`: `Trip` type, status and action labels, `dispatchAmbulance`, `postTripAction`. `src/api/ambulances.ts`:
  status `dispatched`, `trip` on `Ambulance`, `getAmbulances({status, hospitalId})`. `src/api/transfers.ts`: `trip`, `etaMinutes`,
  `TransferMove` (adds `dispatchAmbulance`).
- `features/transfers/DispatchAmbulanceForm.tsx`: the available ambulances at the supplier and the ETA.
- `features/transfers/TripPanel.tsx`: the trip, its times and its step buttons (only those in `trip.actions`).
- `TransferCard` and `TransfersPage`: dispatch and trip steps, refresh the transfer after each move, errors in the alert.
- `AmbulancesPage`: "On trip" status with the transfer and the trip's step.
- `src/test/mockApi.ts` and fixtures: the endpoints above, in the real shape.

### Access

No change to the `ACCESS` table. Trips use `ambulances` (edit, supplier side) for every write and `transfers` for every
read that the transfer detail gives, as the transfer does.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Ambulance `dispatched` status and trip moves; `Trip` model, constraints and migration; manual endpoint refuses trip moves | `apps/ambulances/{models,services,migrations/0002}.py` | `apps/ambulances/tests/test_trips.py` (model constraint, manual refusal) |
| 2 | Trip services: dispatch and step, with locks, audit and rollback; ETA | `apps/ambulances/services.py`, `apps/transfers/services.py` (guard, `lock_transfer`, `via_trip`, case close) | `test_trips.py` (services: rules, rollback, concurrency on PostgreSQL) |
| 3 | API: transfer trip endpoint, trip actions, transfer and ambulance JSON, access | `apps/ambulances/{serializers,views,trip_urls}.py`, `apps/transfers/{serializers,urls,models}.py`, `config/urls.py` | `test_trips.py` (201/400/403/404/409 per endpoint), `apps/transfers/tests/test_api.py` key set |
| 4 | Frontend: API, dispatch form, trip panel, transfer card, page, ambulances page | `src/api/{trips,ambulances,transfers}.ts`, `features/transfers/*`, `pages/staff/{TransfersPage,AmbulancesPage}.tsx`, `features/ambulances/ambulances.ts` | `TransfersPage.test.tsx`, `AmbulancesPage.test.tsx`, `api/trips.test.ts` |
| 5 | Mock API and fixtures | `src/test/mockApi.ts`, `src/test/fixtures/transfers.ts` | covered by unit 4 tests |
| 6 | Docs | `docs/architecture/api.md`, `api-contracts.md`, `erd.md` (Trip has a transfer) | – |

## Sequencing

1 → 2 → 3 (backend, in that order, because the services need the model). 4 and 5 after 3, since the mock mirrors the
shape. 6 with 3 and 4. The spec's receipt flow (B03) is unchanged; a completed trip leaves the transfer in transit for the
receiver to confirm.

## Test plan

- **Dispatch (201/400/403/404/409):** approved only (409); available only (409); base hospital (400); one active trip
  per transfer and per ambulance (409, and the database constraint); permission matrix (nurse and admin at the supplier
  201, doctor and blood bank at the supplier 403, receiver 403, outsider 404, another hospital's ambulance 404).
- **Rollback:** a failure after the transfer and ambulance moves undoes both, with no trip and no audit rows.
- **Concurrency:** two dispatches of one ambulance for two transfers, run at once, on PostgreSQL: one 201, one 409.
  (Skipped on SQLite, as the existing constraint tests are. Not run locally: no PostgreSQL here; runs in CI.)
- **Steps (200/403/404/409):** depart, arrive, complete in order; out-of-order and unknown moves 409 and change nothing;
  receiver 403; outsider 404; a supplier without `ambulances` edit 403.
- **Transfer while a trip is active:** dispatch, start transit, deliver and cancel are 409 with the trip message.
- **Completion:** frees the ambulance; the transfer stays in transit; the receiver then confirms (B03 still works).
- **Ambulance manual moves:** `dispatch` and `release` refused (409); `startMaintenance` on a dispatched vehicle 409.
- **Case close:** closing or cancelling a case with an active trip is 409 and changes nothing.
- **Audit:** `trip.dispatched`, `trip.departed`, `trip.arrived`, `trip.completed`, `ambulance.status_changed`,
  `transfer.dispatched`, `transfer.inTransit`.
- **Frontend:** the dispatch flow, the step buttons for the supplier only, the receiver's read-only trip, the ambulances
  page's trip line and filter, and the 409 path.
- **CI checks** from `AGENTS.md`: ruff, format, `makemigrations --check`, pytest, npm lint/test/build, deploy-config and
  AIDLC board checks.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that approval
is the Construction gate.
