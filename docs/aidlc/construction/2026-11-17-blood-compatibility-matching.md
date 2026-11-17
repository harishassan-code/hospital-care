# Construction Plan: Blood compatibility matching engine

**Spec:** [docs/aidlc/inception/2026-11-17-blood-compatibility-matching.md](../inception/2026-11-17-blood-compatibility-matching.md)
**Date:** 2026-11-17

## Design

- **Rules file:** `backend/apps/matching/blood_compatibility.json`, the one place the rules are written as data.
  - Top level: `_source` (the domain doc), `_doc` (what an entry means), `_order` (how the list is ranked), and
    `components`.
  - `components` maps each component (`redCells`, `plasma`, `platelets`, `cryo`) to every recipient group. Each
    recipient group maps to an ordered list of donor groups, best first, and the identical group is always first.
  - An entry is a donor group code, such as `"O-"`. A platelet entry can be an object, `{"group": "O+", "rhFlag": true}`,
    for an RhD-positive platelet offered to an RhD-negative recipient. Only that case is flagged.
- **Loader and engine:** `backend/apps/matching/compatibility.py`, with no model or migration changes.
  - `load_rules(path=None)` reads and validates the file, then caches the result with `functools.lru_cache`, one
    entry per path. Validation covers: exactly the four components, each with all eight recipient groups and no
    others; every donor a valid group; no duplicate donors; the identical group first. Any failure raises
    `ImproperlyConfigured` with the file path and the problem. The `path` argument is the test hook.
  - `compatible_donors(recipient, component) -> list[DonorOption]`, where `DonorOption` is a frozen dataclass of
    `group`, `rank` (0 is best) and `rh_flag`. An unknown recipient or component raises `ValueError`.
  - `compatible_units(recipient, component, *, exclude_hospital_id=None, now=None)` returns one queryset.
    It applies `usable_units()` from `apps/blood/services.py`, so the usable filter is not written twice. It limits
    the units to the compatible groups and the component, across the whole network. It excludes the requesting
    hospital when asked. It annotates `donor_rank` with a `Case`/`When`, then orders by `donor_rank`, `expires_at`
    and `id`. It is one query.
- **System check:** `backend/apps/matching/checks.py` registers `matching.E001`. It calls `load_rules()` and turns
  an `ImproperlyConfigured` into an `Error`, so `manage.py check` and `runserver` fail. `AppConfig.ready()` imports
  the module to register the check. Gunicorn does not run system checks, so the first load still validates the file
  there.
- **Frontend drift guard:** a test in `frontend/src/features/blood/blood.test.ts` reads the rules file with `node:fs`.
  For each recipient group it asserts that the set of red-cell and plasma donors equals `compatibleDonors()`.
- **Docs:** the domain doc's "Where the rules live" section names the rules file and the drift test.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Rules file, loader and validation, `DonorOption`, `compatible_donors`, `compatible_units`, system check, AIDLC docs, domain doc update | `backend/apps/matching/blood_compatibility.json` (new), `backend/apps/matching/compatibility.py` (new), `backend/apps/matching/checks.py` (new), `backend/apps/matching/apps.py`, `docs/aidlc/inception/2026-11-17-blood-compatibility-matching.md` (new), `docs/aidlc/construction/2026-11-17-blood-compatibility-matching.md` (new), `docs/domain/blood-compatibility.md` | pytest: all 256 component x recipient x donor cases against the doc's rules; identical group first; the platelet flag; loader errors (missing group, bad donor, duplicate, identical not first, unreadable file); the system check fails on a broken file; `compatible_units` excludes unusable units, other components and incompatible groups, works across hospitals, honours `exclude_hospital_id`, orders by rank then expiry then id, runs one query; unknown recipient or component raises `ValueError` |
| 2 | Frontend drift guard | `frontend/src/features/blood/blood.test.ts` | vitest: for every recipient group, red-cell and plasma donor sets in the rules file equal `compatibleDonors()` |

Test file: `backend/apps/matching/tests/test_compatibility.py` (new).

## Sequencing

Unit 1 before unit 2: the drift guard reads the rules file that unit 1 creates. A single PR carries both units,
since the spec fits in one reviewable change.

## Test plan

- `cd backend && pytest apps/matching/` for the new tests.
- The full suite on Postgres and on SQLite.
- `cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run`
  and `DJANGO_DEBUG=true python manage.py check`.
- `cd frontend && npm run lint && npm test && npm run build`.
- No migrations, no API changes, so the API docs are unchanged. The inception spec says the engine has no endpoint.

## Review

This unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge. That approval
is the Construction gate. The inception spec's sign-off is pending the Product Owner.

## Notes from construction (2026-11-17)

- **Verified:** SQLite, full suite: 816 passed, 2 skipped, and one failure that is not this story's
  (`apps/blood/tests/test_donors.py::test_slot_cannot_be_double_booked`, a known SQLite issue). Postgres: 819 passed.
  `makemigrations --check` reports no changes, and `manage.py check` reports no issues. Ruff check and format are clean.
  Frontend: lint clean, 359 tests pass (the 32 in `blood.test.ts` included), and the build succeeds.
- **The rules file is checked both ways.** The 256-case matrix comes from the doc's rules, not from the JSON. Each
  deliberately wrong rules file failed the tests it should, and the drift guard failed on a one-line mismatch in plasma.
- **Red cells put O- last for every recipient, as the spec says.** That differs from the doc's AB order (O first). It is
  one of the open questions in the inception spec.
- **The frontend test reads the file through `process.cwd()`.** `npm test` runs from `frontend/`. In jsdom,
  `import.meta.url` is an http URL, so it cannot give a file path. The test file references node's types locally, since
  the app's tsconfig does not include them.
- **`load_rules` is `functools.lru_cache`, keyed by path.** Its `cache_clear()` is the test hook for the system check.
  Failures are not cached, so a fixed file loads on the next call.
- **Gunicorn does not run system checks.** The shipped file is validated at the first call to `load_rules()` there, and by
  `manage.py check` and runserver everywhere else.
- **Not done here:** no commit, no push. The inception spec's sign-off is pending the Product Owner.
