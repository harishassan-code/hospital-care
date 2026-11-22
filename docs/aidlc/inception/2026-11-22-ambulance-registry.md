# Inception Spec: Ambulance registry

**Date:** 2026-11-22
**Author:** Claude, drafted for review
**Bolt:** [B04](../bolts/B04-ambulance-registry.md)
**Related backlog item:** #50 Ambulance registry (Sprint 8)

## Problem

Transfers (B01–B03) move blood and equipment between hospitals, but nothing records which vehicles exist, where they
are based or whether they're free. Coordinators phone around to find one. This is for nurses and admins, who run the
fleet, and for doctors who need to see what transport capacity exists.

## User stories

- As a coordinator, I want ambulances registered with their base hospital and type, so that transport capacity is
  known. (#50)

## Acceptance criteria

- [ ] An ambulance has an identifier (unique, e.g. `AMB-CG-01`), a type, a base hospital, a status, a plate and an
      optional note.
- [ ] Types: **BLS** (basic life support), **ALS** (advanced life support), **PTS** (patient transport).
- [ ] Statuses: **available**, **on trip**, **maintenance**, **out of service**. Status changes go through a
      `StateMachine`; `on trip` is set and cleared only by dispatch (B05), never by hand.
- [ ] `GET /api/ambulances/` lists ambulances (filters: hospital, type, status); `POST` registers one; `PATCH` edits
      status and note. Own-hospital rule as for equipment: staff manage their own hospital's fleet; admins all.
- [ ] Every registration and status change is audit-logged (`ambulance.registered`, `ambulance.status_changed`).
- [ ] A new `ambulances` module in the access table: admin and nurse edit; doctor view; others none. Same table in
      `permissions.py`, `roles.ts` and `api-contracts.md`.
- [ ] `/staff/ambulances` page with filters and a register form (shaped like the Equipment page), replacing the
      placeholder.
- [ ] `seed_demo` adds 2–3 ambulances per hospital.

## Non-goals

- Dispatch, trips, ETAs (B05). Live GPS. Crew rosters.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Own app or inside transfers?** Proposed: its own app `apps/ambulances`, shaped like `apps/equipment`.
2. **Types?** Proposed: BLS / ALS / PTS as above.
3. **Is an ambulance a `Resource` (reservable stock)?** Proposed: no. It isn't matched to case needs; it's dispatched
   for a transfer. A plain model with its own state machine leaves matching untouched.

## Approval

- [x] Approved by: kabirraj0011 (for the Product Owner) on 2026-11-22
