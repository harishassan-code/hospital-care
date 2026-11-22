# Inception Spec: City command centre dashboard

**Date:** 2026-11-22
**Author:** Claude, drafted for review
**Bolt:** [B09](../bolts/B09-city-command-centre.md)
**Related backlog item:** #55

## Problem

No one can see the whole network at once: which hospital is short of what, what is about to expire, and where the
active emergencies are.

## User stories

- As management, I want a city-wide view of availability, shortages and active emergencies, so that I can monitor
  conditions. (#55)

## Acceptance criteria

- [ ] `GET /api/command-centre/` (admin only) returns, per hospital: free and total beds, ICU free and total, available
      blood units by group, near-expiry blood units (≤ 3 days), equipment available and total, active emergencies by
      severity; plus network totals.
- [ ] A **shortages** list: hospital + blood group below its minimum (the same minimums the Overview uses, moved to
      one backend constant), and hospitals with no free ICU bed.
- [ ] A constant number of queries whatever the hospital count, pinned with a query-count test.
- [ ] `/staff/command-centre` page: network total tiles, one row per hospital, shortages and near-expiry highlighted;
      replaces the placeholder. Admin only in the access table (both places + docs).
- [ ] Refreshes like Overview (B08).

## Non-goals

- Historical trends and charts over time (B18). A new "management" role.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Who is management?** Proposed: admin only. A read-only role would touch every module's access rules; it can be
   added later as a role with `commandCentre: view`.
2. **Near-expiry threshold?** Proposed: 3 days, the same as the blood page's warning.

## Approval

- [x] Approved by: kabirraj0011 (for the Product Owner) on 2026-11-22
