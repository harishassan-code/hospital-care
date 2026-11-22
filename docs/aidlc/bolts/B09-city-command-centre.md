---
id: B09
title: City command centre dashboard
issues: 55
points: 5
priority: high
sprint: 8
depends_on: -
owner: codewithalphadotcom
status: In Review
---

# B09 · City command centre dashboard

**Goal:** Management sees the whole network on one page: availability, shortages, near-expiry units and active emergencies per hospital.

## Stories and acceptance criteria

[#55](https://github.com/harishassan-code/hospital-care/issues/55): As management, I want a city-wide view of availability, shortages and active emergencies so that I can
monitor conditions.

- [ ] Aggregates across all hospitals
- [ ] Highlights shortages and near-expiry units network-wide

## Build on

- `apps/matching/candidates.py` groups stock across hospitals in one query per need; reuse that approach for a single
  aggregate endpoint. `apps/matching/tests/test_candidates_performance.py` shows how to pin the query count.
- Stock minimums and expiry rules already used on Overview (`frontend/src/features/blood/blood.ts`, `attention.ts`).
- Remove `/staff/command-centre` from `planned.ts` when the page lands.

## Scope

- **In:** Aggregate API (admin only), command-centre page, query-count test.
- **Out:** Historical trends (stretch B18).

## Open questions for Inception

- Who is "management"? There's no such role: admin only, or a new read-only role?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-city-command-centre.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-city-command-centre.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-city-command-centre.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
