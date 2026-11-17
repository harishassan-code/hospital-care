# Inception Spec: Allocation record and blood allocation

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog items:** #45 Allocation record, #46 Blood allocation workflow (Epic E4, Sprint 6; builds on
#43 [atomic resource reservation](2026-11-17-atomic-resource-reservation.md), #33
[local availability](2026-11-17-local-availability-check.md), #34 and #35
[request status and escalation](2026-11-17-request-escalation-and-closure.md) and #32
[multi-resource needs](2026-11-17-multi-resource-matching.md))

## Problem

A confirmed reservation is only a hold. It says that a unit, bed, device or room is set aside for a case, but it does not
say that the resource was handed over. When it expires or is released, nothing is left of who received what. The
request's fulfilment count is also never moved, so a case that has its blood in hand still shows as short, and the
blood bank has no single action that moves the unit, the reservation and the case together.

This is for the blood bank and for the staff at the case's hospital who receive or use the stock, and for the emergency
coordinator who reads the case history afterwards.

## User stories

- As staff, I want confirmed reservations turned into allocation records so that there is a permanent history of who
  received what. (#45)
- As blood-bank staff, I want to confirm allocation of reserved units so that inventory and request states update together.
  (#46)

## Acceptance criteria

### #45 Allocation record

- [ ] An allocation links the request, the need, the resource, the hospital that supplies it, the staff member who allocated
      it, the time and an optional note. Each reservation has at most one allocation.
- [ ] Allocations are visible in the case's history. The case detail lists them, and the case timeline shows each one in
      order, next to the status changes.
- [ ] An allocation is permanent. There is no endpoint to change or delete one, and the Django admin shows allocations
      read-only. Its foreign keys are `PROTECT`, so the reservation, need, case, hospital or user can't be deleted under it.
- [ ] Each allocation writes an audit record (`allocation.created`).

### #46 Blood allocation workflow

- [ ] Allocating a held resource runs in one database transaction. The resource moves to its final state, the reservation
      becomes **allocated**, the allocation is recorded, the need's fulfilled count goes up by one and the case status is
      recomputed. If any step fails, nothing changes.
- [ ] Final states: blood unit **issued** (`issue`); bed **occupied** (`admit`, a new move from reserved, with `admittedAt`
      set and the patient fields left blank); equipment **in use** (`use`); operating room **in use** (`startCase`).
- [ ] Allocation is allowed only for a hold that is still held and not past its expiry. Otherwise 409, and nothing changes.
      Allocating the same hold twice is 409.
- [ ] A user may allocate a resource type only with edit rights on its module (blood: `blood`; bed: `beds`; equipment:
      `equipment`; operating room: `operatingRooms`), and only for a resource at their own hospital (admins: any hospital).
      Otherwise 403. A hold at another hospital that the user can't see is 404.
- [ ] Case status after each allocation: the first one moves the case to **partially fulfilled**; the last one, when every
      need is fulfilled, moves it to **fulfilled**. A case that is escalated first goes through **resume matching**. An open
      case goes through **start matching**. The moves are system moves with a note, so the timeline says so.
- [ ] A case that is closed, cancelled or already fulfilled can't take an allocation. Otherwise 409.
- [ ] **Allocate all held units for a need** allocates every held reservation for that need in one transaction. It is
      all-or-nothing: if one of them can't be allocated, none is.
- [ ] The case page's Reservations panel shows an **Allocate** button on each held reservation the user may allocate. Each
      need shows "2 of 4 allocated · 2 remaining". The case status and the remaining count update after allocating.
- [ ] The Blood page has a **Reserved for cases** panel. It lists held blood reservations at the user's hospital, grouped by
      case and need, with **Allocate** per unit and **Allocate all N** per need. Both ask for confirmation first. Errors show
      in the page's alert. After allocating, the list and the stock figures refresh.
- [ ] View-only roles see no Allocate buttons.

## The rules in one place

| Thing | Rule |
|---|---|
| Final state | Blood `reserved` to `issued` (`issue`). Bed `reserved` to `occupied` (`admit`). Equipment `reserved` to `inUse` (`use`). Room `reserved` to `inUse` (`startCase`). |
| Hold | Must be `held` and not past `expires_at`. Ends as `allocated`, with `ended_at` set and `end_reason` "Allocated". |
| Need | `fulfilled` goes up by one per allocation. It can't pass the quantity (database check). |
| Open count | A need's open count is `quantity - fulfilled - held`. Allocated holds are already in `fulfilled`, so they are not counted again. This corrects the #43 notes, which subtracted held and allocated holds. |
| Case move | Held or allocated stock doesn't change the case until allocation. Allocation moves the case through the lifecycle as a system move (no actor), last in the transaction. |
| Who may allocate | Module edit for the resource's type, and `may_change` on the resource (own hospital; admins network-wide). |
| Held list order | Most severe case first, then the case that has waited longest, then the hold that expires first. |
| Bed admission | The bed is occupied, `admittedAt` is the allocation time, and no patient is recorded. Patient details are not part of this story. |

## Non-goals

- Undoing an allocation. A mistake is recorded, and the case or resource is corrected by a new action. There is no
  "unallocate".
- Transfers (#47): sending stock from another hospital through an approval. This story allocates only the holds made at the
  case's own hospital.
- Patient records. A bed is admitted without a patient, because cases hold no patient-identifying data.
- Notifications to the requesting hospital when stock is allocated.
- Allocating pharmacy stock or any other resource outside the four types.
- A scheduled job for holds. The request-time expiry sweep (from #43) runs before every allocation.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **A fulfilled case can't take an allocation.** Its needs are already met, and a later allocation would have nowhere valid
   to move the case. Proposed: 409, the same as closed and cancelled.
2. **Admitting a bed without a patient.** The bed becomes occupied with `admittedAt` set and no patient fields. Proposed:
   keep this. Patient details are added by the ward workflow, which doesn't exist yet.
3. **Manual admit on a reserved bed.** The bed action endpoint gains the `admit` action, so a bed reserved by hand (with no
   hold) can be admitted from the bed board. A bed held for a case is refused there (409), and is admitted through the
   allocation. Proposed: keep this.
4. **Held list order.** Severity first, as the case list does. Then the case that has waited longest, then the expiry. This
   puts the most urgent need first and the hold closest to expiry before others in the same case. Proposed: keep this.
5. **Allocated holds stay visible.** The case's Reservations panel keeps allocated holds, marked allocated, so the history
   of the case is complete. Proposed: keep this.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
