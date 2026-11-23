# Construction Plan: Realistic city network data with history

**Spec:** [docs/aidlc/inception/2026-11-23-realistic-data.md](../inception/2026-11-23-realistic-data.md)
**Date:** 2026-11-23

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | `apps/staffing` (`StaffMember`, `Shift` with `on_duty_at` and `covering`) and `apps/metrics` (`MetricSnapshot`, `catalog.py`), with migrations and read-only admin | `backend/apps/staffing/`, `backend/apps/metrics/`, `config/settings.py` | On duty means clocked in and not out; covering means planned now |
| 2 | The network: seven new hospitals and the wards, rooms, equipment and fleets the first three gain (`apps/core/seed/profiles.py`); equipment, room lists, ambulances, blood stock and donors by profile (`resources.py`) | `backend/apps/core/seed/`, `seed_demo.py` | Counts; every hospital complete (a blood bank has no beds); the scenario's stock exact; Seaview's O− expire first; a re-run adds nothing |
| 3 | Rosters, shifts and clock-ins; on-call consultants at the new hospitals, topped up on every run (`staffing.py`) | `backend/apps/core/seed/staffing.py` | Roster sized to beds; shifts span 14 days back to 7 ahead; clock times only once started; a few late and missed; someone always on call |
| 4 | Two weeks of hourly history ending at the live state, and each emergency department's status read from its last hour (`history.py`) | `backend/apps/core/seed/history.py`, `seed_demo.py` | Every series 336 hours, last point = live figure; arrivals near the profile, busier by day than before dawn; blood never negative; statuses match; a re-run adds nothing |
| 5 | The e2e scenario's two preconditions for the bigger network (S1: the scenario's three among more hospitals; S4: Seaview ranks first); the demo script's steps 1 and 7; docs | `e2e/tests/mvp-scenario.spec.ts`, `docs/` | The scenario passes against a fresh seed |

Refinements of the spec: `--hospitals N` still accepts 3 or more; below 10 it seeds the first N named hospitals.
The first three hospitals keep their own random streams, and what they gain comes from new ones, so none of their
existing data changes.

## Test plan

AGENTS.md checks, the deploy-config and board checks, and the e2e scenario against a fresh seed.

## Review

The PR needs a reviewer's approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md).
