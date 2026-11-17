---
id: B11
title: Donors page for the existing donor API
issues: 20, 21, 22
points: 5
priority: medium
sprint: 8
depends_on: -
owner: unassigned
status: Ready
---

# B11 · Donors page for the existing donor API

**Goal:** Give blood bank staff a page for the donor features whose API shipped in Sprint 3: register donors, record screening and book donation appointments. Today `/staff/donors` still says "coming soon".

## Stories and acceptance criteria

Stories #20 Donor registration, #21 Donor eligibility screening, #22 Donation appointments are done in the backend
(see `backend/apps/blood/tests/test_donors.py`). The missing part is the UI:

- [ ] List and search donors; register a donor and see the generated code
- [ ] Record a screening (deferral reason and until-date) and see eligibility
- [ ] Book and cancel a donation appointment on a free slot

## Build on

- API: `GET/POST /api/blood/donors/`, `GET /api/blood/donors/<code>/`, `POST /api/blood/donors/<code>/screening/`,
  `GET/POST /api/blood/appointments/`, `POST /api/blood/appointments/<id>/cancel/` (`backend/apps/blood/urls.py`).
- `frontend/src/pages/staff/BloodPage.tsx` and `frontend/src/features/blood/` for page and form patterns.
- Replace the `/staff/donors` entry in `frontend/src/features/staff/planned.ts` with a real route and nav item
  (blood bank and admin), in `roles.ts` and `permissions.py`.

## Scope

- **In:** Donors page, forms, API client, tests.
- **Out:** Any backend change beyond small fixes found while building the UI.

## Open questions for Inception

- Separate nav item, or a tab inside Blood bank?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-donors-page.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-donors-page.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-donors-page.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
