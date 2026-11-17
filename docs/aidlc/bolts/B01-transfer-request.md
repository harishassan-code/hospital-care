---
id: B01
title: Inter-hospital transfer request
issues: 47
points: 5
priority: highest
sprint: 7
depends_on: -
owner: unassigned
status: Ready
---

# B01 · Inter-hospital transfer request

**Goal:** A hospital that is short of something can ask another hospital for it from the case page, and the supplying hospital approves (which reserves the stock) or rejects with a reason. This is the first step of the core MVP scenario (reserve → transfer → receive).

## Stories and acceptance criteria

[#47](https://github.com/harishassan-code/hospital-care/issues/47): As a requesting hospital, I want to request resources from another hospital, and as the supplying
hospital approve or reject it, so that shortages are covered while suppliers keep control.

- [ ] Supplier can approve or reject with reason
- [ ] Approval reserves the units; rejection releases them

## Build on

- `backend/apps/transfers/`: empty app, already in `INSTALLED_APPS`. Put the `Transfer` model, services, views and tests here.
- `apps.matching.reservations.reserve(item, *, hospital, quantity, actor)` already reserves at **any** hospital and
  `release(...)` ends a hold. Today only `CaseReservationsView` calls `reserve`, always with `case.hospital`.
- `apps.matching.candidates.candidates_for_case(case)` + the case page's "Sources in the network" panel
  (`frontend/src/pages/staff/EmergencyCasePage.tsx`) already rank the hospitals to request from. Add the
  "Request transfer" action there.
- `apps.audit.services.record(...)` for every change; `apps.accounts.permissions.ACCESS` + `frontend/src/features/staff/roles.ts`
  for a new `transfers` module (keep both tables identical; see `docs/architecture/api-contracts.md`).
- `frontend/src/features/staff/planned.ts`: remove `/staff/transfers` when its real page lands.

## Scope

- **In:** Transfer model (request item, supplier, receiver, quantity, status, reason, who/when), create/approve/reject API, supplier's incoming list, case-page request action.
- **Out:** Status beyond requested/approved/rejected (B02), receiving the stock (B03), ambulances (B05).

## Open questions for Inception

- Holds expire after `RESERVATION_HOLD_MINUTES` (30). Does an approved transfer extend the hold, or move it to a
  separate "committed" state until delivery? (Affects B03.)
- Who approves on the supplier side: the role that may edit that resource's module (blood bank for blood, nurse for beds…)?
- Partial approval (2 of 4 units)? Simplest MVP answer: approve the quantity that's free, like `reserve` does.

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-transfer-request.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-transfer-request.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-transfer-request.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
