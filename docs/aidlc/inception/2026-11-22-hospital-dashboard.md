# Inception Spec: Hospital dashboard: requests, transfers and live refresh

**Date:** 2026-11-22
**Author:** Kabir-Raj-01, drafted with Claude
**Bolt:** [B08](../bolts/B08-hospital-dashboard.md)
**Related backlog item:** #54

## Problem

Overview already shows beds, blood by group and pharmacy, but not the hospital's open emergencies or the transfers
waiting on it, and it goes stale until the page is reloaded.

## User stories

- As hospital staff, I want a dashboard of my inventory, beds, active requests and transfers, so that I see my
  situation at a glance. (#54)

## Acceptance criteria

- [x] Stock by blood group and bed occupancy (already shipped).
- [ ] **Open emergencies** panel: my hospital's cases that aren't fulfilled, closed or cancelled, by priority, with
      severity, shortfall and a link. Shown to roles that can see Emergencies.
- [ ] **Pending transfers** panel: incoming requests waiting for my answer, and transfers on the way (approved /
      dispatched / in transit), with a link to Transfers. Shown to roles that can see Transfers.
- [ ] Staff data refreshes every **60 s** in `StaffProvider` (paused while the tab is hidden) and on window focus,
      without a reload; an "Updated hh:mm" label shows how fresh it is.
- [ ] Tests with the mock API for both panels and the refresh.

## Non-goals

- City-wide view (B09). New backend endpoints (the existing list endpoints are enough).

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Re-estimate from 5 to 3 points?** Proposed: yes, most of the story already shipped.
2. **Refresh interval?** Proposed: 60 s for data; the bell polls faster (B07).

## Approval

- [x] Approved by: Kabir-Raj-01 (author) on 2026-11-22 · Product Owner sign-off: pending
