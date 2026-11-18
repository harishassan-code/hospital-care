# Inception Spec: Delivery confirmation

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B03](../bolts/B03-delivery-confirmation.md)
**Related backlog item:** #49 Delivery confirmation (Epic E6, Sprint 7; builds on #48
[transfer tracking](2026-11-18-transfer-tracking.md) and #45, #46
[allocation](2026-11-17-allocation-record-and-blood-allocation.md))

## Problem

When transferred stock arrives, the receiving hospital has to put it on its own books and give it to the case. Done by
hand, that is several steps (change the unit's hospital, allocate it, update the case), and a failure halfway leaves a
unit that belongs to neither hospital, or a case that still looks short. This completes the core MVP scenario: find,
reserve, transfer, receive.

This is for the staff at the requesting hospital who receive the stock (blood bank for blood, nurses for equipment).

## User stories

- As the requesting hospital, I want to confirm receipt so that inventory moves to my hospital and the request
  updates. (#49)

## Acceptance criteria

- [ ] Staff at the receiving hospital with edit rights on the resource's module (blood: `blood`; equipment:
      `equipment`) can **confirm receipt** of a transfer that is dispatched or in transit. Admins can for any hospital.
      Otherwise 403.
- [ ] Receipt runs in one database transaction. For each unit held for the transfer: the unit's hospital becomes the
      receiver (its storage place is cleared and its location says it was received from the supplier), then it is
      allocated to the case through the existing `allocate`. The need's fulfilled count goes up, an allocation record is
      written for each unit, the case status is recomputed, and the transfer becomes **delivered** with a history entry.
- [ ] If any step fails (for example, a blood unit expired on the way, or the case was closed meanwhile), nothing
      changes: no unit moves, nothing is allocated, the transfer stays where it was, and the answer is 409 with the reason.
- [ ] Receiving a transfer twice is 409 (delivered is final).
- [ ] Each unit's move is audit-logged (`<model>.transferred`, with from and to hospital), along with the allocation
      (`allocation.created`) and the transfer move (`transfer.delivered`).
- [ ] The Transfers page shows **Confirm receipt** on an outgoing transfer (one the user's hospital asked for) that the user may receive, after a
      confirmation prompt. The case page then shows the allocations and the updated remaining count.

## The rules in one place

| Thing | Rule |
|---|---|
| What moves | `hospital` set to the receiver, `storage_location` cleared, `location` set to "Received from <supplier>". |
| Then | `allocate(hold)` for each hold: blood is issued, equipment goes in use, the allocation is recorded and the case recomputed (#45, #46). |
| Allocation's hospital | The supplying hospital, as the allocation record already says "supplied by". |
| Locks | Case, then need, then the transfer, then its holds and resources: the order reservation and allocation already use. |
| Atomic | One `transaction.atomic()`; any exception rolls back every unit. |

## Non-goals

- Receiving part of a transfer (2 of 3 units). Proposed below: all or nothing.
- Putting received units on the shelf instead of straight to the case. The units were requested for this case, so they
  are allocated to it on receipt.
- Ambulance trip completion (B05). It may trigger delivery later, but receipt stays a human confirmation.
- Beds and operating rooms (patient transfer, #63–#65).

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Beds and operating rooms can't physically move.** Proposed: B01–B03 cover blood and equipment only. Beds and
   rooms stay with patient transfer (stretch bolt B17).
2. **Partial receipt?** Proposed: no. Receipt is all or nothing, because the transfer is one shipment. If a unit is
   unusable on arrival, the requester cancels the transfer (its holds are released at the supplier, which then deals
   with the unit) and asks again.
3. **Who confirms receipt?** Proposed: the role that may allocate that type at the receiving hospital (blood bank for
   blood, nurse for equipment), because receipt allocates. A doctor who asked for the transfer can follow it but not
   receive it.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
