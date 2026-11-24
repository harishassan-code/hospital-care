---
id: B21
title: Live city simulation with time controls
issues: -
points: 13
priority: high
sprint: 9
depends_on: B20
owner: harishassan-code
status: Backlog
---

# B21 · Live city simulation with time controls

**Goal:** On staging the network changes by itself the way a real city would: patients arrive and leave, beds turn
over, blood is used and donated, operating rooms cycle, staff clock in and out, emergencies and delays happen, and
waiting times follow. Every change goes through the same rules, audit log and alerts as a person's action.

## Stories and acceptance criteria

From the account owner's request of 23 Nov:

- [ ] An emergency bed is cleared after a low-priority patient is treated and discharged.
- [ ] New patients arrive in random order and priority.
- [ ] Blood is used and donated.
- [ ] Operating rooms are booked, cancelled, in use, cleaned and available again.
- [ ] Doctors and nurses clock in and out.
- [ ] New emergencies and delays happen; waiting times update from the factors that drive them.
- [ ] Patient information stays with the people allowed to see it (with B23).

## Build on

- The state machines (`apps/resources/state_machine.py`), `reserve`/`release`/`allocate`, `apps.audit.services.record`,
  `apps.notifications`, the lazy jobs that already run on request (`escalate_overdue_cases`,
  `release_expired_reservations`), the 30-second staff refresh (`StaffProvider`).

## Scope

- **In:** the simulation engine, an emergency-department queue, staff clock-in, wait estimates, admin pause/resume.
- **Out:** charts (B22); privacy rules beyond what the simulation creates (B23).

## Open questions for Inception

- How does it run on Vercel, which has no background jobs on the free plan?
- Real time or faster?
- How does it stay out of the way of the scripted demo and the end-to-end test?
- How much data does it keep?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/2026-11-23-live-simulation.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/2026-11-23-live-simulation.md` written
- [ ] Code, tests and docs merged; CI green; Definition of Done met
- [ ] Operations notes `docs/aidlc/operations/2026-11-23-live-simulation.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated, issue(s) closed
