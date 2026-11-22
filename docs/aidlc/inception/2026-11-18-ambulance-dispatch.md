# Inception Spec: Ambulance dispatch and trip tracking

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B05](../bolts/B05-ambulance-dispatch.md)
**Related backlog item:** #51 [Ambulance dispatch and trip tracking](https://github.com/harishassan-code/hospital-care/issues/51)
(Sprint 8; builds on #48 [transfer tracking](2026-11-18-transfer-tracking.md), #49
[delivery confirmation](2026-11-18-delivery-confirmation.md) and #50 ambulance registry, whose spec
`2026-11-18-ambulance-registry.md` is being written in parallel)

## Problem

A transfer (#47 to #49) says which hospital sends what, and where it is. Today the supplier's staff move it to
*dispatched* and *in transit* by hand. Nothing records which ambulance carries the stock, when it left, or how long
the trip should take. The coordinator phones around, and the receiving hospital waits without knowing where the
stock is.

The ambulance registry (#50) lists vehicles, but nothing uses them. This story lets a dispatched ambulance drive the
transfer's moves, so the trip and the transfer can't disagree.

This is for the emergency coordinator (doctor or nurse) who arranges transport, the supplier's staff who hand over
the stock, and the receiving staff who wait for it.

**Assumptions.** B02 and B04 are not built yet: `apps/transfers` has no models, and there is no ambulance app. This
spec uses the names from their bolts and from the B04 spec being written in parallel. It assumes a B04 `Ambulance`
with an `identifier`, a `hospital` (its base), a `type`, a `status` of `available`, `dispatched`, `maintenance` or
`outOfService`, and `latitude` and `longitude`. B05 reads the identifier, hospital and status only. It does not use
or move the coordinates. If B04 names things differently, B04 wins. B05 can't start until B02 and B04 are Done.

## User stories

- As a coordinator, I want to dispatch an available ambulance for an approved transfer, so that the stock has
  transport. (#51)
- As a coordinator, I want to follow the trip through its steps (dispatched, en route, arrived, completed), so that
  delivery is coordinated. (#51)

## Acceptance criteria

### Dispatch

- [ ] `POST /api/transfers/<id>/trips/` with `{"ambulance": <id>}` creates a trip and returns it with 201. The trip
      records its transfer, ambulance, status, ETA in minutes, who dispatched it and when.
- [ ] Only an **approved** transfer can get a trip. Otherwise 409.
- [ ] Only an **available** ambulance can be dispatched. Otherwise 409.
- [ ] The ambulance must be based at the transfer's supplying hospital. Otherwise 400.
- [ ] A transfer has at most one active trip, and an ambulance has at most one. A second one is 409. Active means
      dispatched, en route or arrived. The database enforces both with partial unique constraints, as `Reservation`
      does.
- [ ] Dispatch runs in one `transaction.atomic()`. It locks the transfer, then the ambulance (`select_for_update()`).
      It moves the transfer to dispatched through the move function B02 uses for manual moves, moves the ambulance to
      dispatched through `change_status`, and creates the trip. If any step fails, nothing changes.
- [ ] The ETA is `estimated_travel_minutes(hospital_distance(supplier, receiver))` from `apps.matching.distance`,
      rounded to whole minutes. It is stored once, at dispatch.

### Trip steps

- [ ] `POST /api/trips/<id>/actions/` with `{"action": "depart" | "arrive" | "complete"}` moves the trip as the
      lifecycle table says, and returns it (200). Any other move is 409 and changes nothing.
- [ ] Depart moves the transfer from dispatched to in transit through B02's move function. Arrive and complete leave
      the transfer where it is.
- [ ] Complete moves the ambulance back to available through `change_status`. It does not deliver the transfer.
      Receipt stays the receiver's confirmation (B03).
- [ ] While a trip is active, the transfer can't be moved by hand. Dispatch, start transit, deliver and cancel are 409,
      with a message to use the trip.
- [ ] A completed trip is final. Its moves are 409.

### Permissions and errors

- [ ] Dispatching and the trip steps need edit on the `ambulances` module at the supplying hospital (admins: any
      hospital). Otherwise 403.
- [ ] Staff at the receiving hospital can see the trip but can't dispatch it or step it: 403.
- [ ] A transfer that involves neither of the user's hospitals is 404. So is an ambulance the user can't see, and a
      trip whose transfer the user can't see.
- [ ] Each 400, 403, 404 and 409 above has an API test. A test shows that a failing step rolls back the whole dispatch.

### Audit and API

- [ ] Each trip move writes an audit record: `trip.dispatched`, `trip.departed`, `trip.arrived`, `trip.completed`. The
      ambulance and transfer moves write their own records (`ambulance.status_changed`, `transfer.dispatched`,
      `transfer.inTransit`).
- [ ] The transfer detail returns `trip`: its latest trip, or null. Its `actions` list includes `dispatchAmbulance`
      when the user may dispatch one. Each trip returns its own `actions`, so the page shows only the buttons the
      user may press.
- [ ] The `Trip` model lives in B04's ambulance app (`apps/ambulances`), with its migration committed.
      `docs/architecture/api-contracts.md` lists the two endpoints.

### The Transfers page

- [ ] On `/staff/transfers`, an approved outgoing transfer shows **Dispatch ambulance** to users who may dispatch it.
      It opens a choice of the available ambulances at the supplying hospital (B04's list endpoint, `status=available`).
- [ ] The transfer shows its trip: ambulance identifier, status, ETA ("about 25 min") and the time of each step. It
      has **Mark departed**, **Mark arrived** and **Mark completed** buttons, but only the ones in the trip's
      `actions`.
- [ ] After a move, the transfer, its history and its trip refresh. Errors show in the page's alert.
- [ ] `frontend/src/test/mockApi.ts` mocks the new endpoints. The calls go through `frontend/src/api/`.

## The lifecycle

| From | Action | To | Transfer | Ambulance |
|---|---|---|---|---|
| (no trip) | dispatch (`POST …/trips/`) | dispatched | approved → dispatched | available → dispatched |
| dispatched | depart | en route | dispatched → in transit | no change |
| en route | arrive | arrived | no change (stays in transit) | no change |
| arrived | complete | completed | no change | dispatched → available |

The ambulance moves are `dispatch` and `release`. B05 adds both to the ambulance machine from B04. Any other move is
refused.

## The rules in one place

| Thing | Rule |
|---|---|
| Who | Edit on `ambulances` at the supplying hospital (admins: any). The same for every trip step. |
| Which ambulance | Status `available`, based at the supplying hospital. |
| Ambulance status | `dispatched` is set and cleared only by trip moves. B04's manual status actions refuse both (409). |
| Active trip | One per transfer and one per ambulance. Active means dispatched, en route or arrived. |
| Manual moves | The transfer's dispatch, start transit, deliver and cancel are 409 while its trip is active. |
| ETA | `estimated_travel_minutes(hospital_distance(supplier, receiver))`, rounded, stored once at dispatch. |
| Locks | Transfer, then trip, then ambulance. One `transaction.atomic()` per move. |
| Module | `ambulances`, added by B04 to `ACCESS` in `backend/apps/accounts/permissions.py` and to `ACCESS` in `frontend/src/features/staff/roles.ts`. This story adds no module. |

## Non-goals

- Live GPS, maps, or moving the ambulance's coordinates. The ETA is a simulated figure from hospital coordinates.
- A timer or management command that moves trips on its own. Buttons only, for now.
- Pick-up from another hospital, one ambulance on several transfers, or several transfers on one trip.
- Cancelling a trip. Once dispatched, a trip runs to completed.
- Recalculating the ETA during a trip. Crew and patients. Patient transfer is [B17](../bolts/B17-patient-transfer.md).
- Notifications on departure or arrival (B06, B07), and trips on the case page or the dashboard (B08).
- Receiving the stock. That is B03, and completing a trip never triggers it.
- If Sprint 8 runs short, cut this bolt first and keep the registry (B04), as `docs/scrum/timeline.md` says.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Is the trip simulated by a management command on a timer, or by buttons?** Proposed: buttons (Mark departed,
   Mark arrived, Mark completed). They are easier to demo, and there is no scheduler yet, so the escalation command is
   also run by hand. The bolt says arrival moves the transfer to in transit. Proposed instead: departure does, because
   in transit means the stock is on the road. Arrival leaves it in transit, ready for receipt.
2. **Who may dispatch and step a trip?** Proposed: edit on `ambulances` at the supplying hospital (admins: any). [B04](2026-11-18-ambulance-registry.md)
   gives that edit to admin and nurse; doctors can view the trip but not dispatch it. Blood bank doesn't run transport.
3. **Which ambulances can carry a transfer?** Proposed: only those based at the supplying hospital. The ETA is the
   supplier-to-receiver distance, which is right only when the ambulance starts at the supplier. Pick-up from elsewhere
   is a later story.
4. **Can a transfer be cancelled or received while its trip is active?** Proposed: no, 409, until the trip is
   completed. Stock on the road can't be released or received. Completing the trip is the unload, and the receiver
   confirms afterwards (B03).
5. **Does the trip use the ambulance's coordinates?** Proposed: no. The ETA comes from hospital coordinates, and there
   is no live location. This keeps B05 small and avoids GPS, which is out of scope.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
