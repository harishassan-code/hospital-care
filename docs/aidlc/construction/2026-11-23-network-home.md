# Construction Plan: CityCare network home and public hospital pages

**Spec:** [docs/aidlc/inception/2026-11-23-network-home.md](../inception/2026-11-23-network-home.md)
**Date:** 2026-11-23

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Emergency status per hospital: `EmergencyStatus.hospital` (one-to-one) with a data migration that gives the old single row to the first hospital; `update_department_status` service, audit-logged; `GET/PUT /api/emergencies/department/` for the signed-in user's own hospital | `apps/emergencies/models.py`, migration, `services.py`, `views.py`, `case_urls.py`, `serializers.py` | Migration on an existing row; read and update per role; own hospital only; validation; audit entry |
| 2 | Public network: `apps/emergencies/network.py` (`network_snapshot`, `public_hospitals`, `hospital_profile`, availability levels); `GET /api/public/network/`, `/api/public/hospitals/`, `/api/public/hospitals/<id>/`; remove `DoctorShift`, `DoctorSerializer` and `GET /api/public/status/`; `seed_demo` gives each hospital a status | `apps/emergencies/network.py`, `views.py`, `urls.py`; `apps/hospitals` (model, admin, serializer, migration); `seed_demo.py`; permission and security test lists | Levels at their edges; inactive hospitals hidden; 404 for unknown; doctor names only for signed-in staff; no patient fields in any public response; fixed number of queries |
| 3 | Public pages: `api/public.ts`; the network home (`NetworkSnapshot`, `HospitalDirectory` with optional "Use my location", `HowItWorks`, sign-in) and `HospitalPublicPage` at `/hospitals/:id`; the single-hospital landing parts and `api/publicStatus.ts` go | `frontend/src/pages/`, `features/network/`, `features/landing/`, `App.tsx`, `test/mockApi.ts`, fixtures | Page tests (snapshot, directory order, distance sort with a mocked location, failure messages, hospital page with and without names, not found); QA tests updated with `arrayContaining` |
| 4 | Staff: the overview's Emergency tile reads the user's own department; the Emergencies page gets an "Our emergency department" panel to update it | `features/staff/StaffProvider.tsx`, `staffContext.ts`, `features/overview/StatusTiles.tsx`, `pages/staff/EmergenciesPage.tsx`, `api/emergencies.ts` | Tile shows own status, links to the panel; panel saves, shows errors, hidden for roles that can't edit and for staff with no hospital |
| 5 | Docs: API contracts and reference, user manual (public pages), design system (network home), README | `docs/` | Review |

Refinement of the spec: blood levels use the existing red-cell minimums and rule (`RED_CELL_MINIMUM`,
`stock_level`: critical below half the minimum, low below it), summed over the hospitals that keep blood, so the
public level and the command centre agree.

## Sequencing

1 → 2 → 3 → 4 → 5, one commit each where practical, on `claude/complete-project`, one PR for the bolt.

## Test plan

AGENTS.md checks (backend and frontend), the deploy-config and board checks, and the e2e scenario locally against
the built site.

## Review

The PR needs a reviewer's approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md).
