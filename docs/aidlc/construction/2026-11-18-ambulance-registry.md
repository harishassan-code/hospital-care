# Construction Plan: Ambulance registry

**Spec:** [docs/aidlc/inception/2026-11-18-ambulance-registry.md](../inception/2026-11-18-ambulance-registry.md)
**Date:** 2026-11-18

B04 copies the equipment registry (#26) in shape: a `Resource` with an identifier, a type, a hospital and a status, a
`StateMachine` for the status moves, a list and register API, and a page with filters. The differences are the types,
the four moves (no in-use states, those come with B05), no reservations, and a seed of seven vehicles.

## Design

### Model (`backend/apps/ambulances/models.py`)

- `AmbulanceType` (TextChoices): `basic` ("Basic life support"), `advanced` ("Advanced life support"),
  `patientTransport` ("Patient transport").
- `AmbulanceStatus` (TextChoices): `available` ("Available"), `maintenance` ("In maintenance"), `outOfService`
  ("Out of service").
- `AMBULANCE_LIFECYCLE = StateMachine("vehicle", AmbulanceStatus, {...})` with four moves:
  `startMaintenance` (available → maintenance), `finishMaintenance` (maintenance → available), `outOfService`
  (available or maintenance → outOfService), `returnToService` (outOfService → maintenance). Its 409 reads
  "Can't outOfService a vehicle that is out of service."
- `Ambulance(Resource)`: `machine = AMBULANCE_LIFECYCLE`; `identifier` (CharField 40, asset tag), `type` (choices,
  `AmbulanceType`), `status` (choices, default `available`). `hospital` and `status_since` come from `Resource`.
  Meta: ordering `["type", "identifier"]`, index `(type, status)`, and a `UniqueConstraint` on
  `hospital, Lower(identifier)` with `nulls_distinct=False` (same as equipment), so a duplicate tag at a hospital is an
  `IntegrityError` whatever its case.

### Services (`backend/apps/ambulances/services.py`)

Same pattern as `apps/equipment/services.py`.

- `register_ambulance(serializer, actor)`: hospital = the actor's hospital, or `serializer.validated_data["hospital"]`
  for an admin (the API's `hospitalId`, falling back to the admin's own hospital). No hospital at all → `ValidationError
  {"hospitalId": [...]}`. A tag already used at that hospital (case-insensitive) → `ValidationError {"identifier": [...]}`.
  The save catches `IntegrityError` for the race. Audit `ambulance.registered` with identifier, type and status.
- `apply_ambulance_action(ambulance_id, action, *, actor, reason="")`: `@transaction.atomic`,
  `select_for_update()`, `get_object_or_404`, `may_change` (else `Http404`), then `change_status`. The machine's refusal
  (`TransitionNotAllowed`) propagates to the view, which answers 409.

### API (`backend/apps/ambulances/{serializers,views,urls}.py`, mounted at `/api/ambulances/` in `config/urls.py`)

| Method | Path | Does |
|---|---|---|
| GET | `/api/ambulances/?type=&status=&q=` | Own hospital's ambulances (admins: all). `q` matches the identifier. Filters with an unknown value are ignored, as equipment does. |
| POST | `/api/ambulances/` `{identifier, type, hospitalId?}` | Register. 201, or 400 (`identifier`, `hospitalId`, `type`). |
| POST | `/api/ambulances/<id>/actions/` `{action, reason?}` | One of the four moves. 200, 409 (machine's message), 400 (unknown action), 404. |

Permission class `module_permission("ambulances")` on all three views. The serializer's `status` is read-only: a new
ambulance always starts `available`. `hospitalId` is a write-only `PrimaryKeyRelatedField` (source `hospital`); for
non-admins it is ignored, so a user can only register at their own hospital.

### Permissions (`backend/apps/accounts/permissions.py`, `frontend/src/features/staff/roles.ts`)

New module `ambulances` in both tables, identical rows: admin edit, doctor view, nurse edit; blood bank, pharmacist and
patient none. Appended after `operatingRooms` in `MODULES` so the nav reads Equipment, Operating rooms, Ambulances.
`docs/architecture/api-contracts.md` gets an `ambulances` column.

### Frontend

- `src/api/ambulances.ts`: types (`Ambulance`, `AmbulanceType`, `AmbulanceStatus`, `AmbulanceAction`), the label lists,
  `getAmbulances`, `createAmbulance`, `postAmbulanceAction`.
- `src/features/ambulances/ambulances.ts`: `actionsFor(status)` with the four moves (same table as the server).
- `src/features/ambulances/RegisterAmbulanceForm.tsx`: "Register ambulance" button that opens the form (asset tag, type,
  and for admins a "Base hospital" select). The select loads `getHospitals()` only when it is shown, and defaults to the
  admin's own hospital.
- `src/pages/staff/AmbulancesPage.tsx`: the Equipment page's shape. Filters for type and status, "N of M available right
  now.", table `aria-label="Ambulances"` (asset tag, type, base hospital, status, and change-status buttons for editors),
  announcement after a move, 409 reloads the list, 403 says the role can't change ambulances.
- `App.tsx`: `<Route path="ambulances" element={<AmbulancesPage />} />`. `planned.ts`: the `/staff/ambulances` entry is
  removed.
- `src/test/mockApi.ts`: `sampleAmbulances(now)` and routes `GET /ambulances/`, `POST /ambulances/`,
  `POST /ambulances/:id/actions/` in the real response shapes, with the same access gates as the server.

### Seed (`backend/apps/core/management/commands/seed_demo.py`)

`seed_ambulances(hospitals)`: for each hospital, `get_or_create` by `(hospital, identifier)` so a re-run only adds what is
missing. Two per hospital (`advanced`, `basic`) and one `patientTransport` at the main hospital: seven in all, tags
AMB-01 to AMB-07. `--reset` deletes `Ambulance` before `Hospital` (PROTECT).

### Docs

- `docs/architecture/api.md`: a "Ambulances (B04)" section with the endpoints, the shape and the rules; demo data count.
- `docs/architecture/api-contracts.md`: `ambulances` column in the access table.
- `docs/architecture/erd.md`: the Ambulance block names the fields as built (`identifier`, `type`, `hospital`, `status`).

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Model, lifecycle, migration, admin, `ambulances` ACCESS row, app registration | `apps/ambulances/{__init__,apps,models,admin}.py`, `migrations/0001_ambulance_registry.py`, `config/settings.py`, `apps/accounts/permissions.py` | `apps/ambulances/tests/test_ambulances.py` (constraint, lifecycle, status default) |
| 2 | Services, serializers, API, URL mount, audit | `apps/ambulances/{services,serializers,views,urls}.py`, `config/urls.py` | `apps/ambulances/tests/test_ambulances.py` (list, register, actions, 403/404/409) |
| 3 | Seed data and its test counts | `apps/core/management/commands/seed_demo.py`, `apps/core/tests/test_seed_demo.py` | seed counts, re-run, reset |
| 4 | Frontend API, actions, register form, page, route, planned entry, nav and access | `src/api/ambulances.ts`, `src/features/ambulances/*`, `src/pages/staff/AmbulancesPage.tsx`, `src/App.tsx`, `src/features/staff/{roles,planned}.ts`, `src/test/mockApi.ts` | `AmbulancesPage.test.tsx`, `roles.test.ts`, `StaffLayout.test.tsx`, `qa/features.qa.test.tsx` |
| 5 | Docs | `docs/architecture/{api,api-contracts,erd}.md` | – |

## Sequencing

1 → 2 → 3 (backend, in that order: the model before the API before the seed). 4 depends on 2 only for the response shapes
and can follow. 5 goes with 2 and 4. Units 1 and 2 share a branch; each unit is one commit.

## Test plan

Backend (`backend/apps/ambulances/tests/test_ambulances.py`):

- Register: 201 for a nurse at their own hospital (identifier upper-cased, status `available`, audit
  `ambulance.registered`); admin with `hospitalId`; admin with no hospital of their own and no `hospitalId` → 400
  `hospitalId`; nurse with no hospital → 400 `hospitalId`; unknown `hospitalId` → 400; non-admin's `hospitalId` for
  another hospital is ignored (lands at their own); duplicate tag at the same hospital in any case → 400 `identifier`,
  nothing saved, no audit row; same tag at another hospital → 201; bad type or empty tag → 400. The DB constraint
  itself is checked with an ORM insert.
- List: `type`, `status` and `q` filters; a nurse sees only their hospital; admin sees all; a user with no hospital
  sees nothing.
- Actions: each allowed move → 200 with the new status and `statusSince`, audit `ambulance.status_changed` with
  before/after/reason; each refused move (e.g. `finishMaintenance` from available, `outOfService` from out of service) →
  409 with the machine's message and no change or audit row; an action outside the four moves (e.g. `use`) → 400.
- Access: signed-out → 403 on GET, POST and action; blood bank and pharmacist → 403; doctor GET → 200 and POST → 403; a
  patient → 403.
- 404: unknown id; another hospital's ambulance for a nurse; admin without a hospital acting on a hospital's ambulance
  is allowed (200).
- Constraint: a duplicate tag in another case is refused by the database. The check is PostgreSQL-only (SQLite skips
  `nulls_distinct=False` constraints) and runs in CI.

Seed (`apps/core/tests/test_seed_demo.py`): seven ambulances after seeding, two per hospital plus one `patientTransport`
at the main hospital; a re-run adds none; a hospital that lost one gets only that one back; `--reset` starts over.

Frontend:

- `AmbulancesPage.test.tsx`: list with type, base hospital and status; "N of M available right now."; type and status
  filters and the empty state; a nurse registers an ambulance that then appears; required fields and the server's
  duplicate-tag error; an admin picks a base hospital; a doctor sees no register button and no status buttons; a move
  saves through the API, updates the row and announces it; only the moves allowed from the current status are offered;
  a 409 reloads the list and says the status changed first.
- `roles.test.ts`: the access table gains `ambulances`. `StaffLayout.test.tsx`: the admin nav list gains "Ambulances".
- `qa/features.qa.test.tsx`: nurse and doctor nav contain "Ambulances" (`arrayContaining`); blood bank and pharmacist nav
  do not (`not.toContain`); a nurse can open `/staff/ambulances`.
- `App.test.tsx` still passes with one fewer `PLANNED` entry.

CI checks (must be green before the PR): the three command groups in [AGENTS.md](../../../AGENTS.md):

```bash
cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && python -m pytest -q
cd frontend && npm run lint && npm test && npm run build
python3 scripts/check_deploy_config.py && python3 scripts/aidlc_board.py --check
```

Manual check on the seeded demo (`seed_demo`, then sign in as the nurse and as the doctor): the list shows seven
ambulances with their hospitals; the nurse can take AMB-02 (in maintenance) back to service; the doctor has no buttons.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that approval is
the Construction gate.
