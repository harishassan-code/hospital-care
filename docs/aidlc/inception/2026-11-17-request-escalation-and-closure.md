# Inception Spec: Request escalation and closure

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** [#35 Request escalation and closure](https://github.com/harishassan-code/hospital-care/issues/35)
(Epic E4, Sprint 5; builds on [#31 Severity and priority](2026-11-17-emergency-severity-and-priority.md),
[#34 Emergency request status tracking](2026-11-17-emergency-status-tracking.md) and
[#33 Local availability check](2026-11-17-local-availability-check.md))

## Problem

A critical case that nobody fills stays `open` or `matching` with nothing to flag it. The list shows it in the same way
as a case opened a minute ago, so an unfulfilled critical request can be forgotten. A case can also be closed with no
record of how it ended: the close is a status change with an optional note.

This is for the emergency coordinator, and for the staff at the case's hospital who follow cases. The coordinator role
is still an open decision (#9), so the rules here do not name one.

## User stories

- As an emergency coordinator, I want unfulfilled critical requests escalated and fulfilled ones closed, so that nothing
  is forgotten. (#35)

## Acceptance criteria

- [ ] A **critical** case in status **open**, **matching** or **partially fulfilled** is escalated automatically when it has
      stayed in its current status for longer than a configurable time. The default is **30 minutes**.
- [ ] The time is set by the environment variable `EMERGENCY_ESCALATION_MINUTES`. It must be a whole number of 1 or more.
      A bad value stops the server from starting, with a clear message.
- [ ] Automatic escalation writes a timeline entry and an audit record, in the same transaction as the move. The entry has
      no actor, and the timeline shows it as **System**. Its note says why, e.g. "Not fulfilled within 30 minutes (automatic)".
- [ ] A case that is resumed to matching after an escalation gets a fresh window. The window is counted from the time
      the case entered its current status, not from when it was opened.
- [ ] Escalation runs when someone looks at cases (the case list and a case's page), so staff see an up-to-date state
      without a scheduler. A management command, `escalate_overdue_cases`, runs the same check for a scheduler later.
- [ ] Running the check twice escalates nothing the second time.
- [ ] Non-critical cases, and cases that are already escalated, fulfilled, closed or cancelled, are never escalated automatically.
- [ ] Closing a case requires an outcome note. A note of only spaces counts as empty. Without one, the server answers
      **400** `{"note": ["Add an outcome note to close the case."]}` and changes nothing.
- [ ] The outcome note is the note on the close entry in the timeline. The case detail shows it as `outcome`, which is
      `null` for a case that is not closed.
- [ ] A closed case shows its outcome prominently on its page.
- [ ] Escalated cases are labelled with text ("Escalated") in the list and on the case page, not by colour alone.
- [ ] Other moves keep their note optional.

Design decisions that make these testable:

- [ ] The rule is one query for the candidates: critical, active, and the latest status-history entry older than now minus
      the window. When nothing is overdue, the check is that single query.
- [ ] The automatic move goes through the same code as a manual move (`apply_case_action`): the same lifecycle table, the
      same history entry, the same audit record. Only the actor differs (none).
- [ ] Two runs at the same time do not escalate the same case twice. Each candidate is locked with `skip_locked`, and
      its status is checked again under the lock.
- [ ] The close rule lives in the backend, so a client cannot skip it. The page's check is for the person's convenience only.

### The rule for "overdue"

A case is overdue when all of these hold:

| Test | Value |
|---|---|
| Severity | critical |
| Status | open, matching or partiallyFulfilled |
| Time in its current status | the latest timeline entry's time is older than now minus `EMERGENCY_ESCALATION_MINUTES` |

Escalating moves the case to **escalated**. Resuming it moves it back to **matching**, and that move is a new timeline
entry, so the window starts again.

## Non-goals

- A scheduled job. The free Render plan has no cron. The management command is ready for one, and the request-time
  check covers the gap until then.
- Notifying anyone when a case is escalated (no notifications for status changes yet).
- Escalating high, moderate or low cases automatically.
- Choosing a different time for each hospital or each severity. One setting for the whole network.
- Changing the outcome note after the case is closed. The timeline is a record, and closed is terminal.
- Matching: finding units or beds to fill a case. Sprint 6.
- Who may close a case beyond the current rule (anyone who can edit emergencies at the case's hospital). The narrower
  coordinator role waits on #9.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Where the window starts.** Proposed: when the case entered its current status (the latest timeline entry), so a
   case that was resumed gets a fresh window. The alternative is when the case was opened, which would escalate a case
   that was resumed at the last minute as soon as it was resumed.
2. **Which cases the request-time check covers.** Proposed: every hospital's critical cases, whoever is looking. A
   coordinator should not see an overdue case only when the viewer happens to be at its hospital. Escalation is a
   system action, not a view.
3. **"System" for entries with no actor.** An automatic escalation has no actor, as required. A user who has since
   been removed also has no actor (the timeline keeps their entries, with the name gone). So both will show as "System".
   Proposed: accept this for now, since the timeline is only read by staff at the same hospital. A separate label for
   removed users needs a stored field, and would be a follow-up.
4. **Length of the outcome note.** Proposed: the same 500 characters as any note, and at least one non-space character.
5. **Closing from escalated.** Proposed: allowed, as the lifecycle already says. The outcome note is still required.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
