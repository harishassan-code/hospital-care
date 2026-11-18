# Construction Plan: Delivery confirmation

**Spec:** [docs/aidlc/inception/2026-11-18-delivery-confirmation.md](../inception/2026-11-18-delivery-confirmation.md)
**Date:** 2026-11-18

Builds on [transfer tracking](2026-11-18-transfer-tracking.md).

## Design

`receive(transfer, *, actor, note="")` in `apps/transfers/services.py`, one `transaction.atomic()`:

1. Lock the case, the need, then the transfer (`select_for_update`). Check the move is allowed (`deliver` from
   dispatched or in transit) and that `actor` may receive (edit on the type's module at the receiver, or admin):
   403 otherwise.
2. For each held reservation in `transfer.reservations`, lock the resource, set `hospital = receiver`,
   `storage_location = None`, `location = f"Received from {supplier.name}"` (cut to the field's max length), save,
   and record `<model>.transferred` with `before={"hospital": supplier}`, `after={"hospital": receiver}`.
3. `allocate(hold.pk, actor=actor, note=note, transfer_ok=True)` for each hold. That issues blood or puts equipment in
   use, writes the `Allocation` (its hospital stays the supplier), bumps `fulfilled` and recomputes the case.
4. Move the transfer to delivered (history row + `transfer.delivered` audit).

Any exception (`TransitionNotAllowed` for a unit that expired on the way, `AllocationRefused` for a closed case,
`ReservationNotHeld`) rolls the whole transaction back; the view answers 409 with the message.

Frontend: **Confirm receipt** on the Transfers page (outgoing, when `actions` has `deliver`), behind
`window.confirm`, then a refresh. The case page re-reads the case after the move.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | `receive` service and `deliver` action | `apps/transfers/services.py`, `views.py` | `apps/transfers/tests/test_receive.py` |
| 2 | Confirm receipt button | `TransfersPage.tsx` | `TransfersPage.test.tsx` |
| 3 | Seed demo: one approved, in-transit transfer so the demo can show receipt | `apps/core/management/commands/seed_demo.py` | seed test if one exists |

## Sequencing

Last of the three Sprint 7 bolts.

## Test plan

- Receipt moves each unit to the receiver, issues it, writes allocations, fulfils the need and moves the case
  (partially fulfilled / fulfilled), and the transfer is delivered — all in one transaction.
- Rollback: a unit that expired in transit, or a closed case → 409, and the units are still at the supplier, still
  reserved, the transfer status unchanged, no allocation written.
- Receiving twice → 409. Doctor at the receiver can't receive blood (403); blood bank can.
- The full scenario test: create case → candidates → request → approve → dispatch → in transit → receive → case
  fulfilled.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that
approval is the Construction gate.
