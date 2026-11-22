---
id: B17
title: Patient transfer: need check, destination and arrival
issues: 63, 64, 65
points: 5
priority: low
sprint: stretch
depends_on: B01
owner: codewithalphadotcom
status: Done
---

# B17 · Patient transfer: need check, destination and arrival

**Goal:** When a case can't be covered locally, the system suggests moving the patient to the hospital that has everything, and the receiving hospital confirms arrival.

## Stories and acceptance criteria

[#63](https://github.com/harishassan-code/hospital-care/issues/63), [#64](https://github.com/harishassan-code/hospital-care/issues/64), [#65](https://github.com/harishassan-code/hospital-care/issues/65):

- [ ] Flag raised when local availability check fails for critical requirements (partly there: the case page shows the shortfall)
- [ ] Uses multi-resource matching to recommend a destination (partly there: "best single destination" from #42)
- [ ] Arrival confirmation updates case ownership

## Build on

- `apps/matching/multi.py` (`match_hospitals`) and the case page's best-destination panel.
- Case ownership is `EmergencyRequest.hospital`; moving it must keep the history and audit trail.

## Scope

- **In:** Explicit flag, "transfer patient" action, arrival confirmation that moves the case.
- **Out:** Ambulance logistics for patients (B05 covers resources).

## Open questions for Inception

- Points re-estimated from 11 to 5 because most of #63/#64 already shipped; confirm at planning.

## Exit checklist

- [x] Inception spec [`docs/aidlc/inception/2026-11-18-patient-transfer.md`](../inception/2026-11-18-patient-transfer.md) approved (sign-off line filled in)
- [x] Construction plan [`docs/aidlc/construction/2026-11-18-patient-transfer.md`](../construction/2026-11-18-patient-transfer.md) written
- [x] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-patient-transfer.md` written after it's live on staging
- [x] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
