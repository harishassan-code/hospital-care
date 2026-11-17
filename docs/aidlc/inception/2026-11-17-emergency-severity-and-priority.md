# Inception Spec: Emergency severity and priority

**Date:** 2026-11-17
**Author:** Claude, drafted for review
**Related backlog item:** [#31 Emergency severity and priority](https://github.com/harishassan-code/hospital-care/issues/31)
(Epic E4, Sprint 5, 3 pts, priority high; builds on [#30 Create emergency case](2026-11-17-create-emergency-case.md))

## Problem

Cases now record a severity (critical, urgent or routine), but nothing uses it. The case list is newest first, so a
critical case opened at 14:00 sits below a routine one opened at 14:05 and an emergency coordinator has to read every
row to find what matters. The severity scale is also too coarse: "urgent" covers both serious and very time-sensitive
cases, and there is no level for cases that can wait. This is for the emergency coordinator, who triages the list;
doctors and nurses who open cases see the same order.

## User stories

- As an emergency coordinator, I want to classify the severity of a case so that critical cases are handled first.
  (#31)

## Acceptance criteria

- [ ] The severity levels are **critical, high, moderate, low**, in that order of priority. Existing cases are
      kept: `urgent` becomes `high` and `routine` becomes `moderate`. No existing case is `low`, so none changes to it.
- [ ] Case lists (the API list and the Emergencies page) are sorted by **severity, then age**: all critical cases
      first, then high, moderate and low. Within one severity the **oldest case comes first**, because the case
      waiting longest is handled first.
- [ ] A **critical** case is visually distinct on the Emergencies page. The distinction does not rely on colour
      alone: the row has a "Critical" label with an icon and a strong left edge and tint, all from the existing
      status tokens.
- [ ] Every level has a readable label on the list and in the new-case form.
- [ ] The new-case form offers the four levels.

Design decisions that make these testable:

- [ ] The ordering is done by the database in one place (a queryset method used by the list view), so every
      client gets the same order. The page does not re-sort what the server sends.
- [ ] Severity is still chosen when a case is opened. Changing it afterwards is not part of this story.

## Non-goals

- Escalation timers, for example "escalate if not matched within 30 minutes": **#35**.
- Changing a case's severity after it is opened, and status history: **#34**.
- A new public triage scale. The Urgent/Routine categories on the public landing page describe what patients can
  expect, and are not the case severity; they are unchanged.
- Ordering in other lists (matching, allocation, reports). Those arrive with their own stories.
- Per-severity response targets or colour-coded dashboards beyond the Emergencies page.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Age order within a severity.** Proposed: oldest first (the case waiting longest is handled first). The
   alternative, newest first, would match the current list.
2. **Mapping of existing cases.** Proposed: `urgent` becomes `high` and `routine` becomes `moderate`. Nothing becomes
   `low`, because the old scale had no equivalent.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
