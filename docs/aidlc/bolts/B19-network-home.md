---
id: B19
title: CityCare network home and public hospital pages
issues: -
points: 5
priority: highest
sprint: 9
depends_on: -
owner: harishassan-code
status: In Review
---

# B19 · CityCare network home and public hospital pages

**Goal:** The public home page presents CityCare as a city-wide network service, not one hospital's website. Each
member hospital gets its own public page, where its emergency status, departments and who is on duty are shown.

## Stories and acceptance criteria

From the account owner's request of 23 Nov (no GitHub issue yet; created when the spec is approved):

- [ ] The home page explains the network (for patients, hospitals and staff) and shows a live city snapshot and a
      directory of member hospitals with each one's emergency status and wait.
- [ ] No doctor rota or department timetable on the home page; those belong to each hospital's own page.
- [ ] Each hospital has a public page: emergency status and wait, services, departments, who is on duty by
      department, bed availability, contact.
- [ ] Emergency status is per hospital (today it is one row for the whole system).

## Build on

- `frontend/src/pages/LandingPage.tsx` and `features/landing/` (the current single-hospital page), `api/publicStatus.ts`.
- `backend/apps/emergencies/views.py` `PublicStatusView` (anonymous vs staff names, F5) and `EmergencyStatus`.
- `apps/hospitals` (`Hospital`, `Department`, `Capability`, `Bed`), `apps/specialists` (`Specialist`, `OnCallWindow`:
  already per hospital), `apps/blood` low-stock rules (`BLOOD_LOW_STOCK_UNITS`).
- `CityNetwork.tsx` illustration and the Clinical Calm design system.

## Scope

- **In:** home page, public hospital page, per-hospital emergency status, public network and hospital endpoints.
- **Out:** realistic data (B20), anything that changes on its own (B21), charts in the staff workspace (B22).

## Open questions for Inception

- Exact bed counts for the public, or availability levels?
- Sort hospitals by distance? Where is the visitor's location used?
- Doctor names on the public hospital page?
- Who updates a hospital's emergency status?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/2026-11-23-network-home.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/2026-11-23-network-home.md` written
- [ ] Code, tests and docs merged; CI green; Definition of Done met
- [ ] Operations notes `docs/aidlc/operations/2026-11-23-network-home.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated, issue(s) closed
