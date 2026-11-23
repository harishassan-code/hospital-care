---
id: B22
title: Every page with a purpose, an action and charts
issues: -
points: 8
priority: high
sprint: 9
depends_on: B20, B21
owner: harishassan-code
status: Backlog
---

# B22 · Every page with a purpose, an action and charts

**Goal:** Each staff page answers one clear question and leads to the action that follows from it, and the stats
show trends as charts, not just current numbers.

## Stories and acceptance criteria

From the account owner's request of 23 Nov:

- [ ] Every page fulfils the purpose it is there for, not just showing data.
- [ ] Graphs in the stats.
- [ ] Pages for the new live data: the emergency department queue and staff on duty.

## Build on

- `features/overview/OccupancyChart.tsx` and `RedCellChart.tsx` (hand-drawn, palette already validated), the
  design tokens, `StaffDataState`, each page in `pages/staff/`, the command centre (`apps/command_centre`).

## Scope

- **In:** a page-by-page purpose review, a small chart kit, a metrics endpoint, charts and actions on the pages, the
  emergency department and staffing pages.
- **Out:** new modules beyond those two pages.

## Open questions for Inception

- A chart library, or our own?
- Which pages first if time runs short?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/2026-11-23-purposeful-pages.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/2026-11-23-purposeful-pages.md` written
- [ ] Code, tests and docs merged; CI green; Definition of Done met
- [ ] Operations notes `docs/aidlc/operations/2026-11-23-purposeful-pages.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated, issue(s) closed
