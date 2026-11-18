---
id: B03
title: Delivery confirmation
issues: 49
points: 3
priority: high
sprint: 7
depends_on: B02
owner: codewithalphadotcom
status: Done
---

# B03 · Delivery confirmation

**Goal:** The receiving hospital confirms receipt; in one transaction the stock moves to the receiver and is allocated to the case, and the case's fulfilment updates. This completes the core MVP scenario.

## Stories and acceptance criteria

[#49](https://github.com/harishassan-code/hospital-care/issues/49): As the requesting hospital, I want to confirm receipt so that inventory moves to my hospital and the
request updates.

- [ ] Receipt moves units to receiver inventory in one transaction
- [ ] Request fulfilment recalculated

## Build on

- `apps.matching.allocations.allocate(reservation_id, *, actor, note)` already moves a held resource, writes the
  `Allocation` record and recomputes the case (`_recompute_case`) inside `transaction.atomic`. Receipt = change the
  resource's hospital to the receiver, then allocate, in the same transaction.
- `apps/matching/tests/test_allocations.py` shows the rollback-on-failure tests to mirror.

## Scope

- **In:** Receive action + API, atomic hospital move + allocation, case recompute, tests for rollback.
- **Out:** Ambulance trip completion (B05) — it may later trigger *delivered*, but receipt stays a human confirmation.

## Open questions for Inception

- Beds and operating rooms can't physically move: is a "transfer" of a bed really a *patient* transfer (stretch B17)?
  Recommended: B01–B03 cover blood and equipment; beds/ORs stay with patient transfer.

## Exit checklist

- [ ] Inception spec [`2026-11-18-delivery-confirmation.md`](../inception/2026-11-18-delivery-confirmation.md) approved (written; Approval line still says pending)
- [x] Construction plan [`2026-11-18-delivery-confirmation.md`](../construction/2026-11-18-delivery-confirmation.md) written
- [x] Code, tests and docs merged in #102; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-delivery-confirmation.md` written after it's live on staging
- [x] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
