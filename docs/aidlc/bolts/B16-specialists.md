---
id: B16
title: Specialist profiles and on-call availability
issues: 61, 62
points: 5
priority: low
sprint: stretch
depends_on: -
owner: unassigned
status: Ready
---

# B16 · Specialist profiles and on-call availability

**Goal:** Coordinators can see which specialists each hospital has and who is on call now.

## Stories and acceptance criteria

[#61](https://github.com/harishassan-code/hospital-care/issues/61) and [#62](https://github.com/harishassan-code/hospital-care/issues/62):

- [ ] Profile has specialty and hospital
- [ ] On-call schedule per specialist; "Available now" filter

## Build on

- The public home page already lists doctors with department and hours from `seed_demo`
  (`frontend/src/features/landing/DoctorSchedule.tsx`, `/api/public/status/`). Start from that data instead of a new model if it fits.

## Scope

- **In:** Profiles per hospital, on-call times, filter.
- **Out:** Booking specialists.

## Open questions for Inception

- Re-use the public doctor schedule model, or a separate staff-only one?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-specialists.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-specialists.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-specialists.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
