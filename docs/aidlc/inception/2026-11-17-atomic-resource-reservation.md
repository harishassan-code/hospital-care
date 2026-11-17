# Inception Spec: Atomic resource reservation

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog items:** #43 Atomic resource reservation, #44 Concurrency conflict prevention tests (Epic E4,
Sprint 6; builds on #33 [local availability](2026-11-17-local-availability-check.md), #38
[find candidate hospitals](2026-11-17-find-candidate-hospitals.md), #42
[multi-resource matching](2026-11-17-multi-resource-matching.md) and #35
[request escalation](2026-11-17-request-escalation-and-closure.md))

## Problem

Two requests can see the same free unit, bed, ventilator or operating room, and both can plan to use it. The
candidate list and the local availability check only show what is free now. Nothing holds a resource for a case
while staff decide, so a coordinator can send a unit to one case and another coordinator can send the same unit
to a second case.

This is for the emergency coordinator and for the staff at the case's hospital. A reservation holds a resource for
one case, so the other searches stop offering it, and it returns to stock when the hold runs out.

## User stories

- As staff, I want matched resources reserved atomically so that two requests cannot claim the same unit. (#43)
- As the team, we want proven protection against double allocation so that data integrity holds under load. (#44)

## Acceptance criteria

### #43 Atomic resource reservation

- [ ] Reserving stock for a need runs in one database transaction. The case, the need and each resource are locked
      with `select_for_update`, so two reservations cannot take the same resource.
- [ ] A reservation holds its resource for a configurable time. The default is **30 minutes**, set by the environment
      variable `RESERVATION_HOLD_MINUTES`, which must be a whole number of 1 or more (a bad value stops the server).
- [ ] When a hold expires, its resource goes back to its available status (blood unit: available; bed: free;
      equipment and operating room: available), and the reservation becomes **expired**.
- [ ] Expired holds are released before anyone looks at stock: at the start of the candidates list, the case detail
      and the reservation endpoints. A management command, `release_expired_reservations`, runs the same release for
      a scheduler later.
- [ ] A reserved resource disappears from every search: local availability, the candidates for another case, the
      compatible blood units, the matchable equipment and the matchable operating rooms. This follows from the
      resource's status. No search gets a new filter.
- [ ] Staff can reserve local stock for a case ("Reserve N here") and release one of their holds. Both are refused for
      a case at another hospital (404) and for a role without edit rights on emergencies (403).
- [ ] Partial stock is allowed. If fewer resources are free than asked for, the reservation takes what is there and the
      response lists what it took. No free resource at all is a 400.
- [ ] A reservation can never take a need past its quantity. Asking for more than is still unreserved for the need
      (its quantity, less its fulfilled count and its active holds) is a 400.
- [ ] Reserving for an open case moves it to **matching** through the case lifecycle, with a timeline entry.
- [ ] Each reservation, release and expiry writes an audit record. Each status change goes through `change_status`.

### #44 Concurrency conflict prevention tests

- [ ] An automated test fires eight concurrent reservations for the same single unit, each from its own database
      connection and released together. Exactly one succeeds. The test runs on Postgres and must not be skipped there.
- [ ] A second automated test fires eight concurrent reservations for three units, one unit each. Exactly three
      succeed. Both tests are deterministic (checked by repeated local runs).
- [ ] A second active reservation for the same resource is refused by the database (`IntegrityError`). A new hold on
      a resource that was released before is allowed.
- [ ] A need's fulfilled count is refused by the database when it is below zero or above the need's quantity.

### What "negative inventory" means here

Inventory is counted in rows: a resource is one row (a unit, a bed, a piece of equipment, a room), and a need has a
quantity and a fulfilled count. Negative inventory would be any of these:

1. **A resource counted twice.** Two active holds on the same bed, unit, device or room. Two cases would then both
   believe they have it.
2. **A need with more than it asked for.** Fulfilled plus active holds above the quantity.
3. **A fulfilled count below zero.**

The constraints that make each one impossible:

| Case | Guarantee | Enforced by |
|---|---|---|
| 1. Resource counted twice | At most one `held` or `allocated` reservation per resource (content type and object id) | Partial unique index on `matching_reservation`, `WHERE status IN ('held','allocated')`. Works on SQLite and Postgres. |
| 2. Need over its quantity | `fulfilled <= quantity` | Existing `CheckConstraint` `emergencies_item_fulfilled_within_quantity` |
| 2. Need over its quantity, by holds | `fulfilled + active holds <= quantity` | **Application rule, not a database constraint.** A row check cannot add up other rows. `reserve()` checks it under the need's row lock, and the concurrency tests cover it. |
| 3. Fulfilled below zero | `fulfilled >= 0` | `PositiveSmallIntegerField` already creates `CHECK (fulfilled >= 0)` on both SQLite and Postgres (verified), so no second constraint is added. Tested at the database level. |

A database-level sum (`reserved` as a stored counter with `fulfilled + reserved <= quantity`) would make row 2 a
database rule too. It means keeping the counter in step with the holds on every move, so it is left out of this
story and listed under open questions.

### Rules that make these testable

- [ ] Reservations use the matching registry (the candidate querysets from #38) to pick resources. Blood is ordered
      by donor rank, then earliest expiry; the other types by id.
- [ ] Resources that already have an active hold are never picked, even if their status says available. This is the
      second guard against case 1, and it means a stale status cannot create a second hold.
- [ ] Locks are taken in one order: case, need, then resources (with `skip_locked`, so a concurrent reserver skips a
      unit it cannot get and never waits on it). Release and expiry lock the hold, then its resource.
- [ ] Expiry runs as the system (no actor) through the same resource move as a person's release, and is idempotent:
      an expired hold is no longer held.

## The rules in one place

| Thing | Rule |
|---|---|
| Hold time | `RESERVATION_HOLD_MINUTES`, default 30. The hold's `expires_at` is set when it is made. Changing the setting does not move existing holds. |
| Blood units | `available` to `reserved` (`reserve`), back to `available` (`cancelReservation`) |
| Beds | `free` to `reserved` (`reserve`), back to `free` (`cancelReservation`). A reserved bed can't become occupied yet (see open questions). |
| Equipment | `available` to `reserved` (`reserve`), back to `available` (`cancelReservation`), and `reserved` to `inUse` (`use`) |
| Operating rooms | `available` to `reserved` (`reserve`), back to `available` (`cancelReservation`), and `reserved` to `inUse` (`startCase`) |
| Local stock | Local stock means the case's own hospital. Blood is counted exact-match here (#33), but the reservation picks by compatibility (see open questions). |
| Shortfall | A need's shortfall is what is still missing after its fulfilled count and its active holds (held or allocated). A case does not ask other hospitals for stock it already holds here. |
| Case move | Reserving for an open case moves it to matching (system move, timeline entry with no actor). A case that is escalated, matching or partially fulfilled stays where it is. A closed, fulfilled or cancelled case can't reserve. |

## Non-goals

- Allocation (#45): turning a hold into an allocation, and the fulfilled count moving with it. The `allocated` status
  exists so #45 can use it, but nothing sets it yet.
- Transfers (#47): reserving another hospital's stock when that hospital approves a transfer. That story calls the
  same reservation service with the other hospital.
- A scheduled job. The free Render plan has no cron, so the request-time release and the command cover the gap.
- Admitting a patient to a reserved bed. The bed lifecycle has no admit action yet.
- Reserving across the network from the case page. This story reserves at the case's own hospital only.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Blood at the case's own hospital may be a compatible group.** The spec picks blood by donor rank, so exact groups
   come first and compatible ones follow when the exact ones run out. The "Available here" count stays exact-only
   (#33). Proposed: keep this, since the same rule chooses donors across hospitals (#37). The alternative is exact
   groups only at the case's hospital, which needs a second query path.
2. **Manual moves on held resources.** The existing action endpoints (blood, beds) already let staff move a reserved
   unit by hand, and the new equipment and room moves do the same. A hand-cancelled unit can still have an active hold
   row until it expires. Proposed: keep the endpoints as they are in this story, and in a follow-up refuse a manual
   move on a resource with an active hold.
3. **A reserved bed can't become occupied.** The bed lifecycle has no admit action, and no transition goes from
   reserved to occupied. Proposed: #45 adds `reserved` to `occupied` when a reservation is confirmed.
4. **Who the case move is attributed to.** The move is a system move (no actor), as asked, so the timeline shows
   "System". Proposed: keep it, and the reservation's own audit record names the person.
5. **A stored counter for the sum rule.** See "What negative inventory means here". Proposed: leave it to a follow-up
   if the application rule is ever found to leak.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
