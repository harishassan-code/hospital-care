# Inception Spec: Transfer tracking

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B02](../bolts/B02-transfer-tracking.md)
**Related backlog item:** #48 Transfer tracking (Epic E6, Sprint 7; builds on #47
[transfer request](2026-11-18-transfer-request.md) and #34
[emergency status tracking](2026-11-17-emergency-status-tracking.md))

## Problem

Once a supplier approves a transfer, both hospitals need to know where the stock is without phoning each other: has it
left, is it on the road, has it arrived? The case page also needs to show what is coming from elsewhere, so nobody asks
a second hospital for units that are already on their way.

This is for staff at both hospitals: the supplier who sends the stock, and the requesting hospital that waits for it.

## User stories

- As both hospitals, I want to see transfer status so that everyone knows where the resource is. (#48)

## Acceptance criteria

- [ ] A transfer has one of these statuses: **requested**, **approved**, **dispatched**, **in transit**, **delivered**,
      **rejected**, **cancelled**. Moves go through `apps.resources.state_machine.StateMachine`; a move it doesn't allow
      is 409 and changes nothing.
- [ ] Every move is kept in a status history: from, to, action, note, who, and a timestamp. The first entry is the
      request itself. The history is shown oldest first, the same way as the case timeline.
- [ ] The supplier's staff (edit on the resource's module at the supplying hospital, admins anywhere) can move an approved
      transfer to **dispatched** and a dispatched one to **in transit**. A short hop can go straight from dispatched to
      delivered.
- [ ] The requester can **cancel** a transfer up to and including in transit; its holds are released, so the units count
      as the supplier's stock again. Delivered, rejected and cancelled are final.
- [ ] Closing or cancelling a case cancels its unfinished transfers (requested, approved, dispatched, in transit) in
      the same transaction and releases their holds. Pinned holds never expire, so without this a finished case
      would keep the supplier's stock locked.
- [ ] The **Transfers** page (`/staff/transfers`) lists the transfers of the user's hospital, with **Incoming** (asked of
      us) and **Outgoing** (we asked) tabs and a status filter. Admins see the whole network. Each transfer shows the
      case, the need, the other hospital, the quantity (and how many were approved), the status, and its history, with
      the moves the user may make now as buttons.
- [ ] The case page lists the case's transfers and their status, so staff see what is on its way.
- [ ] The API returns the moves the user may make now for each transfer (`actions`), so the page shows only those.
- [ ] Every move writes an audit record (`transfer.dispatched`, `transfer.inTransit`, and so on).

## The lifecycle

| From | Action | To | Who |
|---|---|---|---|
| requested | approve | approved | supplier |
| requested | reject (reason required) | rejected | supplier |
| requested | cancel | cancelled | requester |
| approved | dispatch | dispatched | supplier |
| approved | cancel | cancelled | requester |
| dispatched | startTransit | in transit | supplier |
| dispatched | deliver | delivered | requester (B03) |
| dispatched | cancel | cancelled | requester |
| in transit | deliver | delivered | requester (B03) |
| in transit | cancel | cancelled | requester |

"Supplier" is edit on the resource's module at the supplying hospital. "Requester" for cancel is Emergencies edit at
the receiving hospital. Admins can make any move.

## Non-goals

- Receiving the stock and moving it between hospitals; that is [B03](2026-11-18-delivery-confirmation.md). This story
  only adds the `deliver` move to the lifecycle table.
- Linking an ambulance or a trip (B05), live location, or ETAs.
- Notifications on each move (B06, B07). Live refresh of the dashboard (B08).

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Who moves a transfer to dispatched or in transit before ambulances exist?** Proposed: the supplier's staff, by hand.
   B05 can make an ambulance trip drive these moves later.
2. **Does a cancelled transfer release its holds?** Proposed: yes, through `release`, in the same transaction as the
   move. The units never left the supplier's books (they only move on receipt, in B03), so releasing them is correct
   even after dispatch: what was sent comes back.
3. **Can a transfer be cancelled after dispatch?** Proposed: yes, by the requester (for example, the case was closed or
   the patient moved). The supplier can't cancel an approved transfer; it can only refuse before approving.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
