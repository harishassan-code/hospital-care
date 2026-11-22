---
id: B04
title: Ambulance registry
issues: 50
points: 3
priority: medium
sprint: 8
depends_on: -
owner: codewithalphadotcom
status: In Review
---

# B04 · Ambulance registry

**Goal:** Coordinators see every ambulance with its base hospital, type and status, so transport capacity is known.

## Stories and acceptance criteria

[#50](https://github.com/harishassan-code/hospital-care/issues/50): As a coordinator, I want ambulances registered with their base hospital and type so that transport
capacity is known.

- [ ] Ambulance has identifier, type, base hospital and status

## Build on

- `backend/apps/equipment/` + `frontend/src/pages/staff/EquipmentPage.tsx` + `frontend/src/features/equipment/`:
  the same registry shape (identifier, type, hospital, status, filters, register form). Copy it.
- `apps.resources.state_machine` for status rules; `seed_demo` (`backend/apps/core/management/commands/seed_demo.py`)
  to add a few ambulances per seeded hospital.
- Remove `/staff/ambulances` from `frontend/src/features/staff/planned.ts` when the page lands.

## Scope

- **In:** Model, admin, list/register API, page with filters, seed data.
- **Out:** Dispatch and trips (B05).

## Open questions for Inception

- New `apps/ambulances` app, or inside `apps/transfers`? (Recommended: its own app, like equipment.)
- Ambulance types: basic / advanced life support / patient transport?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-ambulance-registry.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-ambulance-registry.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-ambulance-registry.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
