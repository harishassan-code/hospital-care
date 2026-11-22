# Construction Plan: Patient transfer: need check, destination and arrival

**Spec:** [docs/aidlc/inception/2026-11-18-patient-transfer.md](../inception/2026-11-18-patient-transfer.md)
**Date:** 2026-11-18

B17 is one model, one set of services and one set of endpoints, so it is built on one branch in the order below. Every
unit runs the full checks in `AGENTS.md` before its commit.

## Design

### Model (`backend/apps/emergencies/models.py`, migration `0006_patient_transfer`)

- `PatientTransferStatus` (TextChoices): `requested`, `arrived`, `cancelled`.
- `PATIENT_TRANSFER_LIFECYCLE = StateMachine("patient transfer", ...)`: `(requested, arrive) → arrived`,
  `(requested, cancel) → cancelled`. Arrived and cancelled are final.
- `PatientTransfer`: `request` (FK `EmergencyRequest`, PROTECT, `related_name="patient_transfers"`), `from_hospital`
  and `to_hospital` (FK `hospitals.Hospital`, PROTECT), `status`, `match` (JSON snapshot, default `{}`), `note`,
  `reason` (text, blank), `requested_by` (FK user, PROTECT), `requested_at` (default now), `arrived_by` (FK user,
  null, PROTECT), `arrived_at` (null).
- Constraints: check `from_hospital != to_hospital`; partial unique on `request` where `status = requested`
  (`emergencies_one_open_patient_transfer`). Indexes on `(from_hospital, status)` and `(to_hospital, status)`.
- `EmergencyRequest` gets no field.

### Shared labels (`backend/apps/emergencies/labels.py`, new)

`need_label` moves here from `serializers.py` (it is re-exported there, so existing imports keep working), and so does
the `HospitalMatch` dictionary that `HospitalMatchSerializer` builds (`hospital_match_data`). The services need both to
write the snapshot, and importing the serializers from a service would be a cycle.

### Services (`backend/apps/emergencies/patient_transfers.py`, new)

Every write is `transaction.atomic()`. Lock order: **case → patient transfer → the case's held reservations → the case's
stock transfers → resources** (resources are locked inside `release`). Every path that touches a case locks the case
first, so two moves on one case take turns. Each state change goes through `PATIENT_TRANSFER_LIFECYCLE.next` and writes
one `apps.audit.services.record` row.

| Function | Does | Refusals |
|---|---|---|
| `transfer_flag(case, rows=None)` | Read only: critical and at least one `shortfall > 0` (`local_availability`, holds counted) | none |
| `request_patient_transfer(case, *, destination, note, actor)` | Locks the case. Checks the rules in order, takes the `match_hospitals` entry for the destination as the snapshot, creates the row | 403 no edit or not the case's hospital; 400 no hospital, nothing short, case not reservable, destination is the case's own, inactive, or not in the list; 409 an open transfer already exists |
| `arrive_patient(transfer, *, actor)` | Locks case and transfer. Destination permission, lifecycle, refuses live stock transfers, cancels requested stock transfers, releases unallocated holds, sets `case.hospital`, marks the row arrived | 404 neither hospital; 403 sending hospital; 409 not requested, or live stock transfers (named) |
| `cancel_patient_transfer(transfer, *, actor, reason)` | Locks the transfer. Sending permission, lifecycle, reason required | 404 neither; 403 destination; 400 no reason; 409 not requested |
| `cancel_open_patient_transfer(case, *, actor, reason)` | Called by `apply_case_action` for close and cancel, in the same transaction | none |

Notes:

- `arrive_patient` never re-checks the destination's stock. The patient is already on the way (spec).
- Stock helpers that `arrive_patient` needs are added to `apps/transfers/services.py`: `live_transfers_of_case(case)` and
  `cancel_requested_for_case(case, *, actor, reason)`. The second cancels requested transfers only, with
  `_move`, so its audit and history are the transfers' own. Both are imported late, as `apply_case_action` already does.
- Audit actions: `patienttransfer.requested`, `patienttransfer.arrived`, `patienttransfer.cancelled`,
  `emergencyrequest.hospital_changed`. Arrival also writes `reservation.released` per hold and `transfer.cancelled` per
  stock transfer, through the existing functions.
- `may_act(user, transfer, action)` and `actions_for(user, transfer)`: `arrive` needs edit on emergencies and (admin or
  the destination); `cancel` needs edit on emergencies and (admin or the sending hospital). `visible_to` and
  `in_direction` mirror the transfers module.
- The snapshot is `hospital_match_data(match)` at request time. It stores the rank, score, distance, travel time, the
  covered needs and the unmet needs with what is missing. Labels are stored with it.

### Endpoints

| Method | Path | Body | Success | Permission |
|---|---|---|---|---|
| POST | `/api/emergencies/<reference>/patient-transfer/` | `{destinationId, note?}` | 201 `PatientTransfer` | `module_permission("emergencies")`; the case must be visible (404) |
| GET | `/api/patient-transfers/?direction=incoming\|outgoing&status=` | – | 200 `PatientTransfer[]`, newest first | `module_permission("emergencies")` |
| POST | `/api/patient-transfers/<id>/actions/` | `{action: "arrive" \| "cancel", reason?}` | 200 `PatientTransfer` | `module_permission("emergencies")`; not visible: 404 |

The list and the action sit at the root, `config/urls.py` mounts `apps.emergencies.patient_transfer_urls` at
`/api/patient-transfers/`, so the case route `emergencies/<str:reference>/` can't catch them. The case detail gains
`transferFlag` and `patientTransfers`.

`PatientTransfer` shape: `id, reference, severity, status, from, to, needs` (labels of the case's needs), `match`
(`HospitalMatch`, the snapshot), `requestedBy, requestedAt, arrivedBy, arrivedAt, note, reason, actions`. It never
carries `patientRef`, stock or holds.

### Frontend

- `api/emergencies.ts`: types `PatientTransfer` and `PatientTransferAction`, `transferFlag` and `patientTransfers` on the
  case detail, and three calls: `requestPatientTransfer`, `getPatientTransfers(direction, status?)`,
  `patientTransferAction`.
- `test/mockApi.ts` mocks the three routes with the server's rules (destination in the candidates list, one open
  transfer per case, arrival and cancellation states).
- `features/emergencies/PatientTransferPanel.tsx` (new): the **Transfer patient** form (optional note) and the open
  transfer with **Cancel transfer** (reason required).
- `features/emergencies/IncomingPatients.tsx` (new): **Incoming patients** (requested transfers to this hospital, with
  **Confirm arrival**) and **Outgoing patients**.
- `pages/staff/EmergencyCasePage.tsx`: "Transfer may be needed" notice naming the short needs when `transferFlag`; a
  **Transfer patient** button on the recommended destination row and on each candidate row, shown only to edit on
  emergencies, with a case that has a hospital, is reservable, and has no open transfer; the timeline gains transfer
  entries (requested, arrived as "Arrived at X from Y", and cancelled on the request's row, since the row stores no
  cancel time).
- `pages/staff/EmergenciesPage.tsx`: the two panels beside the cases list.
- `roles.ts` and `planned.ts` don't change. `permissions.py` and `roles.ts` stay identical (`ACCESS` unchanged).

## Decisions taken while planning

These follow the spec's text where it is exact. Where the spec is silent or its parts disagree, the choice is listed here
so the reviewer can check it.

1. **Cancel needs a reason.** The spec says "cancel ... with a reason", so the API answers 400 when `reason` is blank.
   The action body's `reason?` is optional at the JSON level, because `arrive` doesn't take one.
2. **Arrival takes no note.** The spec's action body lists `note?`, but the row has no arrival note field. `arrive` sends
   only `action`. `note` is for the request.
3. **Severity isn't a refusal on request.** The spec's refusal list has no severity rule. The flag is critical only (open
   question 2), but a high or moderate case with a shortage can still be sent, as the spec lists.
4. **Cancelled transfers carry no time.** The spec's fields are `requested_*` and `arrived_*`, so a cancellation has
   no timestamp on the row. The timeline shows it on the request's entry. The audit log has the exact time. Adding
   `cancelled_at` and `cancelled_by` is a one-line follow-up if the PO wants it on the page.
5. **Destination stock isn't checked on arrival.** Spec, edge cases. The snapshot records why the hospital was chosen.
6. **Concurrency tests are PostgreSQL-only.** The race test follows `apps/matching/tests/test_reservation_concurrency.py`,
   which skips on SQLite. AGENTS.md says these run in CI. The deterministic checks (double confirm, second open transfer
   refused by the constraint, arrival after cancel) run on SQLite as well.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Model, lifecycle, migration `0006_patient_transfer`, `labels.py` (moved `need_label`, `hospital_match_data`) | `apps/emergencies/{models,labels,serializers}.py`, migration | `apps/emergencies/tests/test_patient_transfer_model.py`: constraints (distinct hospitals, one open per case), lifecycle table |
| 2 | Services: flag, request, arrive, cancel, close/cancel hook, stock helpers | `apps/emergencies/{patient_transfers,services}.py`, `apps/transfers/services.py` | `test_patient_transfer_services.py`: each refusal, snapshot, flag, arrival (holds, stock blocks, hospital, history, audit), double confirm, cancel after arrive, capacity change after request, close cancels request. `test_patient_transfer_concurrency.py` (PostgreSQL) |
| 3 | API, root route, case detail fields, API docs | `apps/emergencies/{serializers,views,case_urls,patient_transfer_urls}.py`, `config/urls.py`, `docs/architecture/{api,api-contracts}.md` | `test_patient_transfer_api.py`: every endpoint; role matrix; 400, 403, 404, 409 per rule; wrong hospital confirm; list direction and status filters |
| 4 | Frontend API client, mocks, timeline helpers | `src/api/emergencies.ts`, `src/test/mockApi.ts`, `src/test/fixtures/emergencies.ts`, `src/features/emergencies/emergencies.ts` | `src/features/emergencies/emergencies.test.ts` (timeline merge, labels) |
| 5 | Case page: flag notice, Transfer patient, panel, timeline | `src/pages/staff/EmergencyCasePage.tsx`, `src/features/emergencies/PatientTransferPanel.tsx`, `Emergencies.module.css` | `EmergencyCasePage.test.tsx`: notice shown and gone; button per role, per status, on the best row and a candidate row; the request, the cancel and the error states |
| 6 | Emergencies page: incoming and outgoing patients, QA | `src/features/emergencies/IncomingPatients.tsx`, `src/pages/staff/EmergenciesPage.tsx` | `IncomingPatients` and `EmergenciesPage.test.tsx`; `src/qa/features.qa.test.tsx` (arrayContaining, not.toContain) |
| 7 | Tick the met acceptance criteria in the spec | `docs/aidlc/inception/2026-11-18-patient-transfer.md` | – |

## Sequencing

1 → 2 → 3, then 4 → 5 → 6, then 7. Unit 2 needs unit 1's model. Unit 3 needs unit 2's services. The frontend units
depend on the API contract from unit 3, which is written into `api/emergencies.ts` in unit 4 and mocked there. The bolt
file is not edited, and the board is not regenerated.

## Test plan

- **Backend, every unit:** `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check
  --dry-run && python -m pytest -q`. Baseline on `main` at the time of writing: 1246 passed, 5 skipped (PostgreSQL only).
- **Frontend, every unit:** `cd frontend && npm run lint && npm test && npm run build`.
- **Scripts, every unit:** `python3 scripts/check_deploy_config.py && python3 scripts/aidlc_board.py --check`. The
  check mode only compares files; the regenerating form isn't run.
- **Manual (before review):** on staging, a doctor at a hospital with a shortage requests a transfer to the top
  destination, the destination's doctor sees it under Incoming patients and confirms, and the case moves to that
  hospital with its timeline entry.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that
approval is the Construction gate.
