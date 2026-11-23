# Construction Plan: Every page with a purpose, an action and charts

**Spec:** [docs/aidlc/inception/2026-11-23-purposeful-pages.md](../inception/2026-11-23-purposeful-pages.md)
**Date:** 2026-11-23

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | `GET /api/metrics/`: figures by hour or day, families summed, a typical day, own hospital or the network (or each hospital apart); the `metrics` module | `apps/metrics/{read,views,urls}.py`, `permissions.py`, `roles.ts` | Own hospital; families add up; by day counts add and levels average; typical day; network, one hospital, each apart; 404 and 400; every staff role |
| 2 | Emergency department queue: staff actions on a visit through its lifecycle (`staff_action`), the queue endpoints, `ErVisit.handled_by` so the simulation leaves it to staff; the `emergencyDepartment` module | `apps/emergencies/{visits,queue_views,case_urls}.py`, migration `0009`, `apps/simulation/ed.py` | Tags never names; start treatment then admit; no ward bed keeps them here; no emergency bed is a 409; a chair for a minor complaint; another hospital's patient; roles |
| 3 | Staff on duty: status per shift, today's curve, nurse ratios by department, clock in and mark absent (`Shift.absent`); the `staffing` module | `apps/staffing/{views,urls,services}.py`, migration `0002`, `apps/simulation/staff.py` | On duty against the rota; missing; ratios; mark absent then nothing more; another hospital's shift; roles |
| 4 | The chart kit and its tokens: frame with table view, time series with band, tooltip and keyboard, bars with thresholds and stacking, timeline, sparkline | `frontend/src/components/charts/`, `styles/tokens.css` | Chart and table; loading, empty; keyboard reading of every series; figures and flags as words; timeline and sparkline named |
| 5 | Each page's question under its title; the two new pages; charts on Overview, Emergency department, Blood, Beds, Command centre, Operating rooms, Staff on duty, then Emergency cases, Donors, Equipment, Ambulances, Pharmacy, Transfers and Reports | `features/staff/purposes.ts`, `features/charts/`, `pages/staff/` | The new pages' lead, queue order, actions and charts; menus per role; existing page tests kept |
| 6 | Docs: page purposes, API and access tables, ERD | `docs/` | Board and deploy checks |

Refinements of the spec, settled while building:

- The *Emergency department* page also holds *Our emergency department* (the status and *Why this wait*), which stays
  on the Emergencies page too.
- *Equipment*: the actions are the existing status moves (reserve and release are what cases do).
- *Ambulances*: there is no trip-time figure yet, so the second chart is trips per day over 7 days.
- *Command centre*: a hospital that keeps no blood isn't flagged for blood; it would otherwise rank as most strained.
- The emergency department and staff on duty need a hospital; the CityCare admin, who has none, doesn't see them.

## Test plan

AGENTS.md checks, the deploy-config and board checks, and the e2e scenario against a fresh seed. Screens checked in a
browser against a running simulation, light and dark.

## Review

The PR needs a reviewer's approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md).
