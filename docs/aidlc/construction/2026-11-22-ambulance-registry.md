# Construction Plan: Ambulance registry

**Spec:** [docs/aidlc/inception/2026-11-22-ambulance-registry.md](../inception/2026-11-22-ambulance-registry.md)
**Bolt:** [B04](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Model, lifecycle, admin, migration | `backend/apps/ambulances/models.py`, `admin.py`, `migrations/0001_initial.py`, `config/settings.py` | `apps/ambulances/tests/test_ambulances.py`: lifecycle refuses bad moves |
| 2 | List / register / status API, access table | `apps/ambulances/views.py`, `urls.py`, `services.py`, `apps/accounts/permissions.py`, `frontend/src/features/staff/roles.ts`, `docs/architecture/api-contracts.md` | register 201 + audit; other roles 403; own-hospital list and filters; 409 on a refused move |
| 3 | Ambulances page + seed data | `frontend/src/api/ambulances.ts`, `src/pages/staff/AmbulancesPage.tsx`, `src/App.tsx`, `planned.ts`, `seed_demo.py` | `Sprint8Pages.test.tsx`: list, register, maintenance; doctor read-only |

## Sequencing

Backend before frontend within the bolt. Sprint 8 order across bolts: B06 → B07, B04 → B05, B10, B11, B09, B08,
B13, B12 (the end-to-end scenario uses everything before it).

## Test plan

All CI checks green: backend `ruff check`, `ruff format --check`, `makemigrations --check`, `pytest`; frontend
`npm run lint`, `npm test`, `npm run build`; `scripts/check_deploy_config.py` and `scripts/aidlc_board.py --check`.
Then the UAT checklist row for this story (`docs/testing/uat-checklist.md`) on staging.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before
merge — that approval is the Construction gate.
