# Inception Spec: Create an emergency case

**Date:** 2026-11-17
**Author:** Claude, drafted for review
**Related backlog item:** [#30 Create emergency case](https://github.com/harishassan-code/hospital-care/issues/30)
(Epic E4, Sprint 5, 5 pts, priority highest, on the timeline's "never cut" list)

## Problem

Matching (#38, #41), reservation (#43) and transfer (#47) all act on an emergency case, and the system can't
record one yet: `apps/emergencies` only holds the public ER status board. Until a case exists, none of the
Sprint 6–7 work has anything to run on, and the core MVP scenario (reserve → transfer → receive) can't be
demonstrated. This is for the clinical staff who log an emergency: doctors (who stand in for the coordinator
role, see the [wireframes](../../product/wireframes.md)) and admins.

## User stories

- As an emergency coordinator, I want to log an emergency case so that resource fulfilment can begin
  immediately. (#30)
- As an emergency coordinator, I want to say what the case needs (blood, a bed) so that the system can
  search for it. (#32, the part for blood and beds, if the open question below is answered "yes")

## Acceptance criteria

From #30:

- [ ] A case is created in **at most 3 form steps**: 1. severity and optional patient reference,
      2. requirements, 3. review and submit.
- [ ] Each case gets a **unique reference** (`EC-<year>-<4-digit sequence>`, e.g. `EC-2026-0001`) and the
      status **open**.
- [ ] **No patient-identifying data is required.** The patient reference is optional, free-text up to
      30 characters, and the form says not to enter names.

Design decisions that make these testable:

- [ ] The case belongs to the creator's hospital and records who created it, and when.
- [ ] Creating a case is audit-logged (`emergencyrequest.created`), like every other change.
- [ ] Only roles allowed to edit the new `emergencies` module can create cases; roles that may view it see the
      list. The access table is changed in `permissions.py` and `roles.ts`, and
      `scripts/check_shared_rules.py` (if merged) keeps them identical.
- [ ] The staff workspace gets an **Emergencies** module at `/staff/emergencies` with a case list and the
      3-step form, replacing the "planned" placeholder.
- [ ] Status uses the shared `StateMachine`, with only the initial `open` status in this story. The full
      lifecycle and history are #34.

Requirements (blood and beds from #32):

- [ ] A case has 1–10 requirement items. A blood item needs group, component and quantity (1–20); a bed item
      needs a bed type and quantity (1–5).
- [ ] A case can't be submitted without at least one item.

## Non-goals

- Status changes after `open`, status history and invalid-transition handling: **#34**.
- Priority rules and escalation timers: **#31** and **#35**. Severity is only recorded here.
- Equipment and operating-room requirements: those resource types don't exist yet (#26, #28).
- A local availability check, matching or reservation: **#33**, **#38–#43**.
- Patient records of any kind.

## Open questions

Both resolved at sign-off:

1. **Who can create cases?** Admin, doctor and nurse (edit); blood bank and pharmacist (view only). No new
   `coordinator` role yet; that decision (#9) stays open.
2. **Blood and bed requirements (part of #32) in this cycle?** Yes. #32 stays open for equipment and
   operating-room items.

## Approval

- [x] Approved by: Haris Hassan on 2026-11-17
