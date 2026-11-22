# Inception Spec: End-to-end MVP scenario test and UAT checklist

**Date:** 2026-11-22
**Author:** Claude, drafted for review
**Bolt:** [B12](../bolts/B12-e2e-mvp-scenario.md)
**Related backlog item:** #57

## Problem

Each story has unit and API tests, but nothing proves the whole flow works together in a browser, and the Product
Owner has no checklist to accept the MVP.

## User stories

- As the team, we want the MVP acceptance scenario automated, so that a regression in any step fails CI. (#57)
- As the Product Owner, I want a UAT checklist per story, so that I can accept the MVP and sign it off.

## Acceptance criteria

- [ ] An `e2e/` Playwright project (Chromium only) with one scenario on `seed_demo` data:
      1. A doctor at CityCare General creates a critical case needing an ICU bed and O− red cells.
      2. The local check shows the shortfall; candidates list the other hospitals, ranked, with an explanation.
      3. The doctor reserves what is local and requests a transfer of O− from a supplier.
      4. Blood bank staff at the supplier approve, dispatch (with an ambulance once B05 is done) and mark it en route.
      5. Staff at the receiving hospital confirm receipt; the case's need is fulfilled.
- [ ] A CI job on **PRs to `main`** (and manual dispatch): Postgres service, `migrate`, `seed_demo`, `runserver`,
      `vite build && vite preview`, then the test; it uploads the Playwright trace on failure.
- [ ] `docs/testing/uat-checklist.md`: one row per MVP story with steps, the expected result, a Pass/Fail/Notes column
      and a sign-off line for the Product Owner.

## Non-goals

- Load testing (B13). Cross-browser runs. Visual regression.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Every push, or PRs only?** Proposed: PRs to `main` and manual dispatch; it's slower than the unit tests.
2. **The scenario needs a blood bank login at a second hospital.** If `seed_demo` only has staff at CityCare General,
   add one synthetic blood bank user at the supplier hospital.

## Approval

- [x] Approved by: kabirraj0011 (for the Product Owner) on 2026-11-22
