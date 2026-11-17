# Inception Spec: Emergency blood request

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** [#36 Emergency blood request](https://github.com/harishassan-code/hospital-care/issues/36)
(Epic E4, Sprint 5; builds on [#30 Create emergency case](2026-11-17-create-emergency-case.md),
[#31 Severity and priority](2026-11-17-emergency-severity-and-priority.md) and
[#32 requirements](2026-11-17-create-emergency-case.md))

## Problem

When a patient needs blood now, the staff member who sees the need has to open a full emergency case, step through
three screens and fill in patient fields that are not needed for blood. Blood needs are also invisible to the other
hospitals. A blood bank at a neighbouring hospital cannot see that a critical need exists, so fulfilment cannot start
until someone phones around.

This is for hospital staff who need blood (doctors, nurses, admins) and for blood bank and pharmacist staff at every
hospital, who are the people who can fill a request.

## User stories

- As hospital staff, I want to submit a blood request with group, component, quantity and urgency, so that fulfilment
  can start. (#36)

## Acceptance criteria

- [ ] The request is validated: quantity is a whole number from 1 to 20, the blood group and component are supported
      choices, and urgency is one of the four severities. An unsupported or missing value is a **400** with a field
      error, and nothing is saved.
- [ ] A valid request is saved as an emergency case with one blood need. It is returned as **201** with its reference,
      status `open` and its first timeline entry, and it is audit-logged.
- [ ] The request appears in the network request feed: every hospital's active blood requests, most urgent first.
- [ ] A staff member can send a blood request from the Emergencies page in one step. On success they land on the new
      case's page.
- [ ] Roles that can only view emergencies (blood bank, pharmacist) can open the feed, but not send a request.

Design decisions that make these testable:

- [ ] A blood request **is** an emergency case with exactly one blood need. There is no new model. Urgency is the
      case severity (`critical`, `high`, `moderate`, `low`).
- [ ] Submission goes through the existing case endpoint, `POST /api/emergencies/`, and its service. Validation, the
      reference, the `open` status, the first history entry, the audit record and automatic escalation (#35) all
      come from that path. The quick form is only a smaller screen in front of it.
- [ ] The feed is a read-only view of the same cases. It is not stored or copied.

### Urgency

Urgency reuses the case severity, so a blood request is sorted and escalated like any other case. A critical blood
request that nobody fills is escalated after the usual window (#35).

### What the feed shows

The feed is for matching: a blood bank needs to know what is wanted, how much, how urgent, and whether it is still
open. It is not for patients.

| Shown | Why |
|---|---|
| Reference, severity, status, time since the request | To decide what to do first and whether it is still live |
| The hospital's name | So a blood bank knows who to send units to |
| Each blood need: group, component, quantity, how many are already fulfilled | What is wanted |

| Not shown | Why |
|---|---|
| `patientRef`, notes, the timeline | The feed crosses hospitals. Patient-related data stays inside the case's own hospital. |
| Who created the case | Not needed to fulfil it, and it names staff at another hospital |

A case appears in the feed while it is `open`, `matching`, `partiallyFulfilled` or `escalated`. Fulfilled, closed and
cancelled cases do not appear.

## Non-goals

- A new blood request model, or a separate blood request status. The case lifecycle is enough (#34).
- Matching units to a request, reserving them or moving them between hospitals. That is allocation (#45) and the
  matching step (#38).
- Cross-group compatibility (O− for anyone). That is story #37. The request asks for the group named.
- Notifying a blood bank when a request arrives. There are no notifications yet.
- Pagination of the feed. It shows the 100 most urgent; see the ponytail note in the construction plan.
- Patient identity on a request. The feed and the form collect none.
- Bed requests in the quick form. The feed can show bed needs (`?type=bed`), but a bed request is sent from the full
  case form, as before.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Who sees other hospitals' requests.** Proposed: every signed-in staff member with emergencies access (every staff
   role). Blood banks at other hospitals are the audience, so the feed cannot be limited to the user's own hospital.
   A patient cannot see it.
2. **Whether the feed shows the hospital's name.** Proposed: yes, with its id. The name tells a blood bank where to send
   units. The id lets the page tell the user's own hospital apart, without comparing names.
3. **Whether the feed names who made the request.** Proposed: no. Staff names at other hospitals are not needed to fill
   a request, and the feed is the widest view the app has.
4. **Limit of 100.** Proposed: the 100 most urgent. A network of a few hospitals stays well under it. Paging waits until
   the network grows.
5. **Bed requests from the quick form.** Proposed: no. The quick form is for blood (the story's scope). Beds stay in the
   full case form.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
