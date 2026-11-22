# Inception Spec: Donors page

**Date:** 2026-11-22
**Author:** Kabir-Raj-01, drafted with Claude
**Bolt:** [B11](../bolts/B11-donors-page.md)
**Related backlog item:** #20, #21, #22 (backend done in Sprint 3)

## Problem

The donor API exists and is tested, but blood bank staff have no screen for it: `/staff/donors` says "coming soon".

## User stories

- As blood bank staff, I want to register donors, record screenings and book appointments in the app, so that I don't
  need the admin site. (#20–#22)

## Acceptance criteria

- [ ] `/staff/donors` lists donors with search (name, code) and a blood group filter; shows code, group and
      eligibility (eligible, or deferred until a date).
- [ ] Register form; on success it shows the generated donor code.
- [ ] Donor detail: record a screening (pass, or a deferral reason and until-date); eligibility updates.
- [ ] Appointments: list upcoming; book a free slot for an eligible donor; cancel. API errors shown inline.
- [ ] Nav item "Donors" for the roles that can see the blood module's donor endpoints (blood bank and admin), in both
      access tables + docs; placeholder removed. Endpoints mocked in `mockApi.ts`; page tests.

## Non-goals

- Backend changes beyond small fixes found while building. Donor self-service.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Separate nav item or a Blood bank tab?** Proposed: a separate nav item "Donors", next to Blood bank.
2. **New access module?** Proposed: only if the donor endpoints don't already use the `blood` module. If they do, keep
   `blood` and add just the nav item, so access stays one rule.

## Approval

- [x] Approved by: Kabir-Raj-01 (author) on 2026-11-22 · Product Owner sign-off: pending
