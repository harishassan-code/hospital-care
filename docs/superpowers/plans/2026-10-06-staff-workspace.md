# Staff workspace: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the staff shell (preview roles), Overview dashboard, Beds, Blood bank and Pharmacy pages.

**Architecture:** `/staff` is a layout route. `StaffProvider` loads beds, blood units, medicines and ER status once
and holds the preview role, so every page and the bell read one store. Domain rules live in pure, tested
modules (`lib/time`, `features/staff/roles`, `features/beds/beds`, `features/blood/blood`,
`features/pharmacy/pharmacy`, `features/staff/attention`). Pages are thin compositions of small components.

**Tech Stack:** React 19, React Router 7 (layout + index routes), CSS Modules, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-06-staff-workspace-design.md`

## Global Constraints

- No commits until the user approves. Branch `feat/staff-workspace` (stacked on #71).
- Colours only from tokens; status always shown as icon + text, never colour alone.
- Sample data generators are deterministic (seeded) and take `now`, so tests can fix the clock.
- Same quality floor as the landing work: keyboard, focus, labels, AA contrast, 375px with no sideways scroll.
- Lint, tests and build pass at every checkpoint.

## Tasks

1. **Shared time + reuse refactor.** Move generic helpers (`toMinutes`, `minutesOfDay`, `formatClock`,
   `shiftSegments`, `isInNow`) from `features/landing/schedule.ts` to `lib/time.ts`, add `currentShift`,
   `formatDuration`, `hoursUntil`; move `useNow` to `lib/useNow.ts`; extract the department filter into
   `components/ui/FilterBar` and use it in `DoctorSchedule`. Tests: `lib/time.test.ts`.
2. **Roles.** `features/staff/roles.ts`: `Role`, `Module`, `ROLE_LABEL`, `MODULES`, `canSee`, `canEdit`.
   Tests per spec table.
3. **Beds domain + sample data.** `api/beds.ts` (seeded generator), `features/beds/beds.ts`: `actionsFor`,
   `applyAction`, `cleaningMinutes`, `isCleaningOverdue`, `summarize`, `dischargesToday`. Tests.
4. **Blood domain + sample data.** `api/blood.ts`, `features/blood/blood.ts`: `compatibleDonors`,
   `stockStatus`, `sortFefo`, `availableCounts`, shelf life and storage tables. Tests incl. full red-cell and
   plasma compatibility matrices.
5. **Pharmacy domain + sample data.** `api/pharmacy.ts`, `features/pharmacy/pharmacy.ts`: `onHand`,
   `daysOfSupply`, `nearestExpiry`, `isBelowReorder`, `expiresWithin`, `filterMedicines`. Tests.
6. **Attention rules.** `features/staff/attention.ts`: `buildAttention` per spec rules, sorted. Tests.
7. **Shell.** `StaffProvider` + `useStaff`, `StaffLayout` (sidebar, top bar, preview banner, access guard),
   `StatusBadge`, `Panel`. Tests: role switch hides nav, bell count, access denied.
8. **Overview page** with tiles, attention list, occupancy chart, red-cell chart (dataviz rules), discharges.
   Test: tiles and attention render from store.
9. **Beds page.** Filters, ward sections, bed tiles, action menu. Tests: discharge → cleaning; doctor sees no
   actions.
10. **Blood page.** Stock grid, compatibility finder, unit table with filters. Tests: O− recipient → O− only;
    AB+ plasma recipient → AB only.
11. **Pharmacy page.** Filters, search, table, batch expansion. Tests: below-reorder filter, batch expand.
12. **Review + visual check.** Code review pass, screenshots at 1280 and 375, fix, final lint/test/build.
