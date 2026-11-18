# Inception Spec: Inter-hospital transfer request

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B01](../bolts/B01-transfer-request.md)
**Related backlog item:** #47 Inter-hospital transfer request (Epic E6, Sprint 7; builds on #38
[find candidate hospitals](2026-11-17-find-candidate-hospitals.md), #43
[atomic resource reservation](2026-11-17-atomic-resource-reservation.md) and #45, #46
[allocation](2026-11-17-allocation-record-and-blood-allocation.md))

## Problem

The case page already ranks the other hospitals that can cover a shortfall (#38, #41, #42), but staff can only reserve
stock at the case's own hospital. Getting blood or a ventilator from the hospital that has it still means a phone call,
and nothing records who asked, who agreed or what was set aside. The supplying hospital also has no say: its stock
shouldn't leave the shelf until its own staff agree.

This is for the emergency coordinator (doctor or nurse) at the hospital that is short, and for the staff at the
supplying hospital who own that stock (blood bank for blood, nurses for equipment).

## User stories

- As a requesting hospital, I want to request resources from another hospital, and as the supplying hospital approve or
  reject it, so that shortages are covered while suppliers keep control. (#47)

## Acceptance criteria

- [ ] A transfer asks one hospital for a quantity of one need of one case. It records the case's need, the supplying
      hospital, the receiving hospital (the case's hospital), the quantity asked for, its status, who asked and when.
- [ ] Staff at the case's hospital with edit rights on Emergencies can request a transfer from the case page's **Sources
      in the network** panel: **Request transfer** on a hospital in a short need's list, with a quantity that starts at
      the smaller of the shortfall and what that hospital has.
- [ ] The request is refused (400, nothing saved) when: the supplier is the case's own hospital; the need is a bed or an
      operating room; the case is fulfilled, closed or cancelled; or the quantity is more than the need has left after
      its fulfilled units, its holds and the transfers still waiting for an answer.
- [ ] A new transfer is **requested**. Nothing is reserved yet, so the supplier's stock stays free until it answers.
- [ ] The supplier can **approve**. Approval reserves the units at the supplier through the existing `reserve`, in one
      transaction. If the supplier has fewer free than asked, it reserves what is free (partial approval); if none is
      free, approval is refused (409) and the transfer stays requested.
- [ ] The supplier can **reject** with a reason (required). A rejected transfer reserves nothing.
- [ ] The requester can **cancel** a transfer that is requested or approved. Cancelling an approved transfer releases its
      holds, so the units go back on the supplier's shelf.
- [ ] Only the supplier's staff can approve or reject: edit rights on the resource's module (blood: `blood`; equipment:
      `equipment`) at the supplying hospital. Admins can act for any hospital. Otherwise 403; a transfer that involves
      neither of the user's hospitals is 404.
- [ ] Every change writes an audit record (`transfer.requested`, `transfer.approved`, `transfer.rejected`,
      `transfer.cancelled`).
- [ ] The supplier sees incoming requests on a new **Transfers** page (`/staff/transfers`), which replaces the placeholder.

## The rules in one place

| Thing | Rule |
|---|---|
| What can be transferred | Blood units and equipment. Beds and operating rooms don't move; that is patient transfer (#63–#65). |
| Who requests | Emergencies edit, at the case's hospital (admins: any). |
| Who answers | Edit on the resource's module, at the supplying hospital (admins: any). |
| Quantity | 1 up to `quantity − fulfilled − held − requested (unanswered) transfers` for that need. |
| Approval | Calls `reserve(item, hospital=supplier, quantity, actor)`. Partial approval keeps what was free. |
| Holds on an approved transfer | Don't expire after `RESERVATION_HOLD_MINUTES`, and can't be released or allocated from the case page. Only the transfer moves them (cancel releases them; receipt in B03 allocates them). |
| New module | `transfers`: admin, doctor, nurse and blood bank have edit; pharmacist has none. The per-action checks above narrow it down. |

## Non-goals

- Any status after approved (dispatched, in transit, delivered). That is [B02](2026-11-18-transfer-tracking.md) and
  [B03](2026-11-18-delivery-confirmation.md).
- Ambulances (B05). Notifications to the supplier (B06, B07): for now the supplier sees the request on the Transfers
  page.
- Pharmacy stock, beds and operating rooms.
- Asking several hospitals in one request. Each hospital gets its own transfer.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Does an approved transfer's hold expire after 30 minutes?** Proposed: no. Delivery can take longer than a hold, and
   a hold that ran out mid-delivery would put a unit in a van back on the supplier's shelf. The hold stays until the
   transfer is cancelled or received. It is not a new reservation status: the hold stays `held` and the expiry sweep
   skips holds that belong to a live transfer.
2. **Who approves on the supplier side?** Proposed: the role that may edit that resource's module there, so the blood
   bank approves blood and nurses approve equipment, the same rule allocation uses (#45).
3. **Partial approval (2 of 4 units)?** Proposed: yes, approve what is free, as `reserve` already does. The transfer
   shows "2 of 4 approved", and the case can ask another hospital for the rest.
4. **Is anything reserved when the request is made?** Proposed: no. The story says approval reserves, and the supplier
   stays in control of its stock until it answers. Unanswered requests do count against the need's quantity, so the same
   units can't be asked for twice.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
