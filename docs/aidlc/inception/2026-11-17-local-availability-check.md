# Inception Spec: Local availability check

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** #33 Local availability check (Epic E4, Sprint 5; builds on
[#30 Create emergency case](2026-11-17-create-emergency-case.md) and
[#34 Emergency request status tracking](2026-11-17-emergency-status-tracking.md))

## Problem

A case lists what it needs (blood of a group and component, or beds of a type), but the coordinator cannot see what the
case's own hospital already has. Every need is therefore treated as something to request from other hospitals, even when
the blood or the bed is on the shelf downstairs. This is for the emergency coordinator, and for the doctors and nurses who
open cases and follow them.

Availability is only shown here. Nothing is reserved, allocated or requested: matching (#38) and allocation (#45) come later.

## User stories

- As an emergency coordinator, I want to see what my own hospital already has so that I only request externally what is
  missing. (#33)

## Acceptance criteria

- [ ] Each requirement on the case page shows the **locally available** quantity at the case's hospital.
- [ ] Each requirement shows its **shortfall**: the quantity still needed after what is available here and what has
      already been fulfilled. The shortfall is never negative. A requirement with no shortfall reads "Covered locally".
- [ ] The case page has a summary line: "Everything is available here" when no requirement is short, otherwise how many
      units or beds are needed from other hospitals.
- [ ] The case's shortfalls are carried to the matching step: a backend function returns only the short requirements, with
      their shortfall, and the matching story (#38) calls it.
- [ ] The case detail API carries the figures. The case list does not, so the list stays cheap.

Design decisions that make these testable:

- [ ] **"Local" means the case's hospital** (`case.hospital`). A case with no hospital has 0 available for every need.
- [ ] **Blood counts exact matches only.** A unit counts when its hospital is the case's, its group equals the need's group,
      its component equals the need's component, its status is **available**, and it has not expired (its expiry is after
      now). Expiry follows the blood app's own rule (`expires_at > now`, the same filter as the stock view). Units that are
      quarantined, reserved, issued, discarded or expired do not count.
- [ ] **Beds count free beds only.** A bed counts when its hospital is the case's, its type equals the need's type and its
      status is **free**.
- [ ] **Compatibility is not applied here.** A need for O− red cells is counted against O− units only, not against any
      group that O− can receive. Cross-group compatibility (for example O− for anyone) is deliberately left to story #37,
      the compatibility matching engine, which will rank and allow substitutes. So a local O− unit does not count toward
      an A+ need even where the compatibility rules would allow it. This undercounts what the hospital could give; the
      shortfall is then larger than strictly necessary, never smaller.
- [ ] **Shortfall** = `max(0, quantity − fulfilled − available)`. `fulfilled` is set by allocation (#45) and is 0 until then.
- [ ] **Computed on read, not stored.** Stock changes constantly, so availability is worked out each time the case detail is
      read. No model field is added.

## Non-goals

- Reserving or allocating local stock to the case. Allocation is **#45**; until then availability is information only.
- Cross-group blood compatibility, and ranking substitutes. **#37**.
- Matching the shortfall against other hospitals, and requesting it from them. **#38** (Sprint 6).
- Availability on the case list. The list stays as it is.
- Availability at other hospitals, or across the network.
- A stored or cached availability figure, and any notification when stock changes.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Exact match only, until #37.** Proposed: yes. Counting compatible groups here would duplicate the rules #37 owns,
   and the blood compatibility table (`docs/domain/blood-compatibility.md`) has no matching engine yet. The cost is that the
   shortfall can be overstated for blood. The page's wording says "available here" to mean that exact stock.
2. **What the summary counts.** Proposed: one total over blood units and beds together ("3 units/beds needed from other
   hospitals"), since the coordinator asks the same question of both. The alternative is a total per resource type.
3. **Expiry margin.** Proposed: a unit that expires at the current moment no longer counts, the same rule as the stock view.
   No "near expiry" margin is applied to the local count.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
