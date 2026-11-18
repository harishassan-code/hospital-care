---
id: B02
title: Transfer tracking
issues: 48
points: 5
priority: high
sprint: 7
depends_on: B01
owner: codewithalphadotcom
status: In Review
---

# B02 · Transfer tracking

**Goal:** Both hospitals see where a transfer is, with a status history, so nobody has to phone to ask.

## Stories and acceptance criteria

[#48](https://github.com/harishassan-code/hospital-care/issues/48): As both hospitals, I want to see transfer status so that everyone knows where the resource is.

- [ ] States: requested, approved, dispatched, in transit, delivered, rejected, cancelled
- [ ] Status history with timestamps

## Build on

- `apps.resources.state_machine.StateMachine`: the same allowed-transition helper the resource and case lifecycles use.
- `apps.emergencies.models.RequestStatusChange` + the case page's "Status history" timeline: copy the pattern
  (a row per change with actor, note, time) for `TransferStatusChange`.
- `/staff/transfers` page: incoming and outgoing transfers for the user's hospital, with filters by status.

## Scope

- **In:** State machine, history, list/detail API and the Transfers page (incoming/outgoing).
- **Out:** Receipt and inventory move (B03); linking an ambulance (B05).

## Open questions for Inception

- Who may move a transfer to *dispatched* / *in transit* before ambulances exist (B05)? Supplier staff, by hand?
- Should a cancelled transfer release its holds automatically? (Recommended: yes, through `release`.)

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-transfer-tracking.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-transfer-tracking.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-transfer-tracking.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
