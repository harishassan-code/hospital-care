# Inception Spec: Find candidate hospitals

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** #38 Find candidate hospitals (Epic E4, Sprint 6; builds on
[#33 Local availability check](2026-11-17-local-availability-check.md),
[#37 Blood compatibility matching](2026-11-17-blood-compatibility-matching.md),
[#39 Distance and travel time](2026-11-11-distance-and-travel-time.md) and
[#32 Requirements](2026-11-17-emergency-blood-request.md))

## Problem

A case says what it needs. The coordinator can see what the case's own hospital has (#33), and what is still short. What
is missing is the other half: which hospitals in the network can supply the shortfall, how much each has, and how far away
they are. Without it the coordinator has to phone around. This is for the emergency coordinator, who requests from the
hospitals this story lists.

Requirements are not limited to blood and beds. Equipment (ventilators, monitors, defibrillators, dialysis machines) and
operating rooms (by capability) are shared resources too, so the same search has to work for all four. The requirement
types for equipment and operating rooms are part of #32, which was waiting for those resource stories. They are added here
because the search needs them.

This story lists candidates. It does not rank them (#41), score them (#40), reserve stock at another hospital, or send a
request to one. Those come later.

## User stories

- As an emergency coordinator, I want hospitals that can supply a needed resource listed so that I can request from them.
  (#38)
- As an emergency coordinator, I want a case to ask for equipment and operating rooms as well as blood and beds, so that the
  whole of a case's shortfall can be sourced. (#32, completed here)

## Acceptance criteria

- [ ] The search works for **blood, beds, equipment and operating rooms** through one shared path over the resource model.
- [ ] A case can list an **equipment** need (type of equipment, quantity) and an **operating room** need (capability,
      quantity). Both show in the New case form and on the case page, with labels such as "2 × Ventilator" and
      "1 × Operating room (cardiac)".
- [ ] Local availability (#33) counts matchable equipment of the type and matchable operating rooms with the capability at the
      case's hospital, so the shortfall for these needs is right.
- [ ] For each short requirement, the case page lists the **other hospitals** that have it: how many they have, whether that
      covers the shortfall, how far away they are, and for blood the earliest expiry.
- [ ] A requirement with no other hospital having it says "No other hospital has this right now".
- [ ] Search over the seeded demo network returns in **under 1 second**, and does a fixed number of queries.

Design decisions that make these testable:

- [ ] **One registry, one generic search.** Each requirement type maps to a queryset of matchable resources of a `Resource`
      subclass: blood through `compatible_units` (#37), beds that are free of the type, equipment that is available of the
      type, operating rooms that are available with the capability. The search groups them by `hospital_id` and counts. It
      works for any of them because they all share `Resource`'s hospital foreign key.
- [ ] **The requesting hospital is excluded.** Its own stock is already counted locally (#33).
- [ ] **Inactive hospitals are excluded.** `Hospital.is_active` is the existing "deactivated" flag, and matching leaves
      deactivated hospitals out, as its own model note says.
- [ ] **Hospitals with nothing to give are omitted.** Only hospitals with at least one matchable resource are listed.
- [ ] **Covers.** A candidate covers the shortfall when its available count is at least the shortfall. A candidate that
      covers less is "partial".
- [ ] **Distance and travel time** come from #39: straight-line distance, and the estimated travel time at the default
      speed. Both are empty when the case has no hospital or either hospital has no coordinates.
- [ ] **Order is plain and deterministic:** covering candidates first, then nearest first (a candidate with no distance comes
      last), then hospital id.
      Scoring (#40) and ranking (#41) replace this later and are not pre-empted here.
- [ ] **Blood** candidates also carry the earliest expiry among their matching units, and the best donor rank (0 is the
      identical group, higher is a compatible substitute), both from #37.
- [ ] **Computed on read, not stored**, as #33 is. Stock changes constantly.
- [ ] **Visibility follows the case.** The candidates are for a case the user can see under the same own-hospital rule as
      the case detail. Another hospital's case is 404.

## Non-goals

- Ranking and scoring candidates, and a weighted order. **#40** and **#41**.
- Reserving, allocating or requesting stock from another hospital. **#45** and the request flow after it.
- Paging the candidates. The list is short because it is per requirement and per hospital.
- Real road routing or traffic. Travel time is still the simulated estimate from #39.
- A stored candidate list, or any notification when another hospital's stock changes.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Requirements share stock at this hospital, but not across hospitals.** Proposed: local availability (#33) still shares
   stock in list order, and a multi-capability operating room is claimed by one line only. Candidates are shown per
   requirement, so two lines can both count the same unit at another hospital. Allocation (#45) is where stock is claimed.
   The cost is that the coordinator may see one unit offered for two lines.
2. **Equipment and operating room limits per line.** Proposed: equipment 5 per line (as beds), operating rooms 3 per line.
   An operating room is a larger request than a bed, so the lower limit is deliberate.
3. **Feed.** Proposed: the network feed (#36) accepts the two new types, so a blood bank can see equipment and room
   requests too. The feed's type query accepts `equipment` and `operatingRoom` as well as `blood` and `bed`. The
   alternative is to keep the feed to blood and beds.
4. **Equipment and operating room needs carry only their own field.** Proposed: a need sends only the field of its type
   (`equipmentType` or `capability`). Other fields it sends are ignored and stored blank, as blood and bed fields already are.
5. **Operating room capability is a match on the room's own list.** Proposed: a room counts for a capability when that code is
   in its capabilities, so a cardiac room with general is a candidate for both. Within one case it covers one line only
   (question 1).

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
