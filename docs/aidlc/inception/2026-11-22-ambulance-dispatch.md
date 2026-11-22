# Inception Spec: Ambulance dispatch and trip tracking

**Date:** 2026-11-22
**Author:** Claude, drafted for review
**Bolt:** [B05](../bolts/B05-ambulance-dispatch.md)
**Related backlog item:** #51 (builds on [B02 transfer tracking](2026-11-18-transfer-tracking.md) and
[B04 ambulance registry](2026-11-22-ambulance-registry.md))

## Problem

A transfer can be marked dispatched and in transit (B02), but not *by what*. The supplier needs to send a specific free
ambulance, and both hospitals need to follow the trip until it arrives.

## User stories

- As a coordinator, I want to dispatch an ambulance for a transfer and track the trip, so that delivery is
  coordinated. (#51)

## Acceptance criteria

- [ ] A **trip** links one ambulance to one transfer, with a status, an ETA in minutes and a timestamp per step.
- [ ] Trip states: **dispatched → en route → arrived → completed**, plus **cancelled**, through a `StateMachine`.
- [ ] Only an **available** ambulance can be dispatched (otherwise 409). Dispatch locks the ambulance row
      (`select_for_update`) so two dispatches can't take the same one; it goes **on trip**.
- [ ] Dispatching an approved transfer with an ambulance moves the transfer to **dispatched** (existing
      `transfers.services.dispatch`) in the same transaction. **En route** calls `start_transit`.
- [ ] Ambulances come from the supplier's fleet; admins may use any. The supplier-side transfer rights apply.
- [ ] **Arrived** marks the trip arrived; the receiver then confirms receipt (B03). Receipt **completes** the trip and
      frees the ambulance. Cancelling the transfer cancels the trip and frees the ambulance.
- [ ] ETA from `apps.matching.distance.estimated_travel_minutes` between the two hospitals.
- [ ] Trip status and ambulance are shown on the transfer in the Transfers page, with a button for the next step.
- [ ] Each step is audit-logged (`trip.dispatched`, `trip.en_route`, `trip.arrived`, `trip.completed`,
      `trip.cancelled`).

## Non-goals

- Maps, GPS, live positions. Patient transport (B17). Timed automatic simulation.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Simulated by a timer or by buttons?** Proposed: buttons ("En route", "Arrived"). Easier to demo and test; no
   scheduler needed.
2. **Is an ambulance required to dispatch a transfer?** Proposed: optional. Dispatch without one still works (hand
   delivery), so B02/B03 and their tests stay as they are.

## Approval

- [x] Approved by: kabirraj0011 (for the Product Owner) on 2026-11-22
