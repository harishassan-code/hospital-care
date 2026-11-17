---
id: B05
title: Ambulance dispatch and trip tracking
issues: 51
points: 5
priority: medium
sprint: 8
depends_on: B02, B04
owner: unassigned
status: Backlog
---

# B05 · Ambulance dispatch and trip tracking

**Goal:** A coordinator dispatches an available ambulance for a transfer and follows the (simulated) trip.

## Stories and acceptance criteria

[#51](https://github.com/harishassan-code/hospital-care/issues/51): As a coordinator, I want to dispatch an ambulance for a transfer and track the trip so that delivery is
coordinated.

- [ ] Only available ambulances can be dispatched
- [ ] Trip states: dispatched, en route, arrived, completed (simulated)

## Build on

- `Transfer` + its state machine from B01/B02: dispatching moves the transfer to *dispatched*, arrival to *in transit* → ready for receipt.
- `apps.matching.distance.estimated_travel_minutes` for an ETA.
- `apps/emergencies/management/commands/escalate_overdue_cases.py`: pattern for a command that advances simulated trips.
- `select_for_update` as in `apps/matching/reservations.py`, so one ambulance can't be dispatched twice at once.

## Scope

- **In:** Trip model and states, dispatch API with the availability check, simulation command, trip status on the transfer page.
- **Out:** Live GPS or maps.

## Open questions for Inception

- Simulated by a management command on a timer, or by buttons ("mark arrived") for the demo? (Buttons are easier to demo.)

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-ambulance-dispatch.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-ambulance-dispatch.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-ambulance-dispatch.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
