# Construction Plan: Transfer tracking

**Spec:** [docs/aidlc/inception/2026-11-18-transfer-tracking.md](../inception/2026-11-18-transfer-tracking.md)
**Date:** 2026-11-18

Builds on the model and services from [the transfer request plan](2026-11-18-transfer-request.md).

## Design

- `TRANSFER_LIFECYCLE` already holds every move (the table in the spec). This bolt adds the services for
  `dispatch(transfer, *, actor, note="")` and `start_transit(transfer, *, actor, note="")` (supplier side), and lets
  `cancel` run from dispatched and in transit.
- The action endpoint routes `dispatch` and `startTransit` to them. `actions` in every response lists only the moves
  that the lifecycle allows from the current status **and** the user may make.
- Transfers page `src/pages/staff/TransfersPage.tsx` at `/staff/transfers`: **Incoming** / **Outgoing** tabs (tabs
  are links with `aria-current`, so they work without JS state), a status `<select>` filter, one card per transfer
  (case reference linked to the case page for the receiver, need, other hospital, "2 of 4 approved", status badge in
  words), a `<details>` history, and the move buttons from `actions`. Reject and cancel open a reason field; reject
  needs it.
- Status words: Requested, Approved, Dispatched, In transit, Delivered, Rejected, Cancelled.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | dispatch / startTransit / cancel-after-dispatch services, actions | `apps/transfers/services.py`, `views.py` | `apps/transfers/tests/test_tracking.py` |
| 2 | Transfers page, route, nav | `TransfersPage.tsx`, `App.tsx`, `features/transfers/` | `TransfersPage.test.tsx`, QA test |

## Sequencing

After the request plan's units. Before delivery confirmation.

## Test plan

- Every allowed move works and writes one history row with actor and time; every other move is 409 and changes nothing.
- Supplier staff can dispatch; requester staff can't (403). Requester can cancel from in transit; holds released.
- History is oldest first; `actions` matches role and side.
- Page: tabs, filter, buttons per `actions`, reject needs a reason, errors shown in the page alert.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that
approval is the Construction gate.
