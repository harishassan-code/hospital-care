# Construction Plan: Inter-hospital transfer request

**Spec:** [docs/aidlc/inception/2026-11-18-transfer-request.md](../inception/2026-11-18-transfer-request.md)
**Date:** 2026-11-18

B01, B02 and B03 share one model and one lifecycle, so they are built on one branch in this order. This plan has the
data model and the request/answer moves; [transfer tracking](2026-11-18-transfer-tracking.md) and
[delivery confirmation](2026-11-18-delivery-confirmation.md) add the rest.

## Design

### Model (`backend/apps/transfers/models.py`)

- `TransferStatus` (TextChoices): `requested`, `approved`, `dispatched`, `inTransit`, `delivered`, `rejected`,
  `cancelled`. `LIVE = (approved, dispatched, inTransit)`: the statuses whose holds are pinned.
- `TRANSFER_LIFECYCLE = StateMachine("transfer", TransferStatus, {...})` with the table in the tracking spec.
- `Transfer`: `request_item` (FK `emergencies.RequestItem`, PROTECT, `related_name="transfers"`), `supplier` and
  `receiver` (FK `hospitals.Hospital`, PROTECT), `quantity` (PositiveSmallInteger, check `> 0`), `status`, `reason`
  (text, blank: why rejected or cancelled), `requested_by` (FK user, PROTECT), `created_at`, and `reservations`
  (M2M `matching.Reservation`, `related_name="transfers"`, blank). Check constraint `supplier != receiver`. Index on
  `(status)`, `(supplier, status)`, `(receiver, status)`.
- `TransferStatusChange`: `transfer` (FK, CASCADE, `related_name="history"`), `from_status`, `to_status`, `action`,
  `note`, `actor` (nullable), `at`. Same shape as `emergencies.RequestStatusChange`.

### Services (`backend/apps/transfers/services.py`)

All writes are `@transaction.atomic`, take locks in the order case → need → transfer → holds → resources, write a
history row through one `_move(transfer, action, *, actor, note)` helper, and call `apps.audit.services.record(actor,
"transfer.<status>", transfer, before=..., after=..., reason=...)`.

- `request_transfer(item, *, supplier, quantity, actor, note="")`. Refuses with `TransferRefused` (400) as the spec
  lists. Pending quantity = sum of `quantity` of the need's `requested` transfers.
- `approve(transfer, *, actor)`: `reserve(need, hospital=supplier, quantity=transfer.quantity, actor=actor)`, add the
  holds to `transfer.reservations`, move to approved. `ReservationUnavailable` → `TransferConflict` (409).
- `reject(transfer, *, actor, reason)`: reason required (`TransferRefused`, 400).
- `cancel(transfer, *, actor, reason="")`: `release(hold, actor=actor, reason=..., transfer_ok=True)` for each held
  hold, then move.
- `may_act(user, transfer, action) -> bool` and `actions_for(user, transfer) -> list[str]`: supplier side = edit on
  `ALLOCATION_MODULE[type]` and (admin or `user.hospital_id == supplier_id`); requester side for cancel =
  edit on `emergencies` at the receiver; for deliver = edit on the type's module at the receiver.

### Changes to `apps.matching`

- `release(reservation, *, actor, reason, transfer_ok=False)`: refuses (`ReservationNotHeld`, 409, "This hold is part
  of transfer #N; cancel the transfer instead.") a hold that belongs to a live transfer unless `transfer_ok`.
- `allocate(reservation_id, *, actor, note="", transfer_ok=False)`: the same refusal, and with `transfer_ok` the
  expiry check is skipped.
- `release_expired`: `.exclude(transfers__status__in=LIVE)` so pinned holds are never swept.
- `transfers` is imported lazily inside these functions (as `apps.resources.services` does), so there is no import
  cycle.
- `ReservationSerializer` gains `transfer` (`{id, status}` or null), and `canAllocate` is false for a pinned hold.

### API (`backend/apps/transfers/urls.py`, mounted at `/api/transfers/`)

| Method | Path | Does |
|---|---|---|
| GET | `/api/transfers/?direction=incoming\|outgoing&status=` | Transfers where the user's hospital is supplier (incoming) or receiver (outgoing); admins see all. |
| POST | `/api/transfers/` `{itemId, supplierId, quantity, note?}` | Request. 201, or 400. Case must be at the user's hospital (404 otherwise). |
| GET | `/api/transfers/<id>/` | One transfer with history and `actions`. 404 if neither hospital is the user's. |
| POST | `/api/transfers/<id>/actions/` `{action, reason?, note?}` | approve, reject, dispatch, startTransit, deliver, cancel. 403 / 409 / 400 as the specs say. |

Permission class `module_permission("transfers")` on all four. New module `transfers` in `ACCESS` (backend and
frontend): admin, doctor, nurse, bloodBank edit. Case detail gains `transfers` (the case's transfers, newest first).

### Frontend

- `src/api/transfers.ts`: types and calls. Mocked in `src/test/mockApi.ts`.
- `roles.ts`: `transfers` module, nav entry "Transfers" at `/staff/transfers`, ACCESS as above. Remove it from
  `planned.ts`.
- Case page: **Request transfer** on each source row of a blood or equipment need (Emergencies edit only), with a
  quantity field; a **Transfers** panel listing the case's transfers with status.
- Pinned holds in the Reservations panel show "In transfer #N" and no Release/Allocate.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Model, lifecycle, migration, admin (read-only history inline) | `apps/transfers/{models,admin}.py`, migration | model constraints |
| 2 | Services: request, approve, reject, cancel; matching changes | `apps/transfers/services.py`, `apps/matching/{reservations,allocations}.py` | `apps/transfers/tests/test_request.py` |
| 3 | API + access table | `apps/transfers/{serializers,views,urls}.py`, `config/urls.py`, `accounts/permissions.py`, emergencies serializer | `apps/transfers/tests/test_api.py` |
| 4 | Frontend: API, case page action and panel, roles | `src/api/transfers.ts`, `EmergencyCasePage.tsx`, `roles.ts`, `planned.ts`, `mockApi.ts` | `EmergencyCasePage.test.tsx`, QA test |
| 5 | Docs | `docs/architecture/api.md`, `api-contracts.md` | – |

## Sequencing

1 → 2 → 3 → 4. Docs with 3. B02 and B03 follow on the same branch.

## Test plan

- Request: happy path; own hospital, bed/OR need, closed case, too many (counting fulfilled, held and pending) → 400.
- Approve reserves at the supplier (units go reserved, hidden from other searches); partial approval; nothing free → 409.
- Reject needs a reason; reserves nothing. Cancel after approval releases the holds.
- Pinned holds: not swept by `release_expired` after 30 minutes; case-page release and allocate are 409.
- Permissions: doctor at the supplier can't approve blood (403); blood bank at the supplier can; another hospital → 404.
- Audit rows written for each move. History rows with timestamps.
- CI: the three check commands in `AGENTS.md`.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that
approval is the Construction gate.
