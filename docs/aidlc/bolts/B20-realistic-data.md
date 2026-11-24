---
id: B20
title: Realistic city network data with history
issues: -
points: 3
priority: high
sprint: 9
depends_on: B19
owner: harishassan-code
status: In Progress
---

# B20 · Realistic city network data with history

**Goal:** Staging looks like a real city network: about ten made-up hospitals in real Karachi areas, with capacities,
occupancy, blood, equipment, operating rooms, ambulances, staff rosters and medicines in realistic proportions, and
two weeks of history so every chart has data from the first deploy.

## Stories and acceptance criteria

From the account owner's request of 23 Nov:

- [ ] The data shown is as close to the real thing as a synthetic data set can be, with the proportions documented.
- [ ] Doctors and nurses have rosters (shifts), per hospital.
- [ ] Two weeks of hourly history per hospital for the charts in B22.
- [ ] Still entirely synthetic: no real patients, staff or hospitals.

## Build on

- `apps/core/management/commands/seed_demo.py` (three hospitals, `--hospitals N`, `--reset`, the demo scenario's
  guaranteed stock) and its tests; `docs/setup/demo-script.md` (the data the demo relies on).

## Scope

- **In:** seed data, staff rosters, metric history, a short document of the proportions used.
- **Out:** the data changing on its own (B21).

## Open questions for Inception

- How many hospitals, and which kinds?
- Keep the three current hospital names?
- How much history?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/2026-11-23-realistic-data.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/2026-11-23-realistic-data.md` written
- [ ] Code, tests and docs merged; CI green; Definition of Done met
- [ ] Operations notes `docs/aidlc/operations/2026-11-23-realistic-data.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated, issue(s) closed
