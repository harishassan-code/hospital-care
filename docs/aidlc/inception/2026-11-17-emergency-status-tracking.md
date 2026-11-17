# Inception Spec: Emergency request status tracking

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** [#34 Emergency request status tracking](https://github.com/harishassan-code/hospital-care/issues/34)
(Epic E4, WBS 4.3, Sprint 5, 5 pts, priority highest; builds on [#30 Create emergency case](2026-11-17-create-emergency-case.md)
and [#31 Severity and priority](2026-11-17-emergency-severity-and-priority.md))

## Problem

A case is opened as `open` and nothing moves it. Staff who opened it cannot tell whether the blood or beds it asked for
are being found, whether it has stalled, or whether it is finished. The seven statuses exist in the data model, but no
action changes them and nothing records who changed what, or when.

This is for the staff who open cases and follow them: doctors and nurses at the case's hospital, and admins. The
emergency coordinator's role is an open decision (#9), so the rules here do not name one.

Statuses move by hand in this story. Fulfilment set automatically from allocation arrives with #45, and matching
itself with the Sprint 6 stories.

## User stories

- As hospital staff, I want to track a request's status so that I know whether it is being fulfilled. (#34)

## Acceptance criteria

- [ ] A case has one of seven statuses: **open, matching, partially fulfilled, fulfilled, escalated, closed, cancelled**.
- [ ] The case page (`/staff/emergencies/<reference>`) shows a **status timeline**: every entry in time order, oldest
      first, with the time, the move (from → to), who made it and the note if there is one.
- [ ] Staff with edit access to emergencies can move a case with buttons for the moves that are valid from its current
      status only. Each move takes an optional note of up to 500 characters.
- [ ] A refused move changes nothing and writes no timeline entry. Any move from **closed** or **cancelled** is refused.
      The page says why.
- [ ] Opening a case writes its first timeline entry (open, action "create"). Cases opened before this story get the
      same entry from a data migration, at their creation time.
- [ ] Every move writes a timeline entry **and** an audit-log entry, in the same transaction.
- [ ] Staff who can only view emergencies (blood bank, pharmacist) see the status and timeline, and no move buttons.
- [ ] Staff move only cases at their own hospital. Admins can move any hospital's case. Another hospital's case is
      reported as not found (404), not as forbidden.

Design decisions that make these testable:

- [ ] The moves are one table in the backend (`REQUEST_LIFECYCLE`, in the same shape as the bed and blood lifecycles).
      The server decides whether a move is allowed. The page only offers the moves the server says are valid.
- [ ] The timeline is the server's order. The page does not re-sort it.

### The moves

| From | Action | To |
|---|---|---|
| open | startMatching | matching |
| matching | partiallyFulfil | partially fulfilled |
| matching | fulfil | fulfilled |
| partially fulfilled | fulfil | fulfilled |
| open, matching, partially fulfilled | escalate | escalated |
| escalated | resumeMatching | matching |
| fulfilled, partially fulfilled, escalated | close | closed |
| open, matching | cancel | cancelled |

**Closed** and **cancelled** are terminal: no move leaves them. Any other pair is refused.

## Non-goals

- Fulfilment set from allocation (reservations filling the case's items): **#45**. Until then staff set fulfilled and
  partially fulfilled by hand.
- Escalation timers ("escalate if not matched within 30 minutes"), and the outcome note that closing will need then:
  **#35**.
- Matching: finding compatible units or beds in the network. Sprint 6.
- Changing a case's severity or its needs after it is opened.
- Editing or deleting timeline entries. The timeline is a record.
- Notifications when a status changes.
- Filtering or sorting the case list by status.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Who can close or cancel a case.** Proposed: anyone with edit access to emergencies at the case's hospital, the
   same as opening one. The alternative is a narrower role, which waits on the coordinator role (#9).
2. **Outcome note on close and cancel.** Proposed: optional here, like every note. The ERD's "outcome note required to
   close" belongs to #35 with escalation.
3. **Fulfilling straight from matching.** Proposed: allowed. A case can be filled in full in one step, so
   `matching → fulfilled` is a move, not a shortcut around the partial state.
4. **Admins at another hospital.** Proposed: an admin with a hospital can move any hospital's case, as the spec's admin
   rule says. The read rule is unchanged, so that admin cannot open the case's page. Decide whether reads should follow
   the same rule.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
