# Construction Plan: City command centre dashboard

**Spec:** [docs/aidlc/inception/2026-11-18-city-command-centre.md](../inception/2026-11-18-city-command-centre.md)
**Date:** 2026-11-18

Bolt B09, issue #55. One aggregated read for admins: every active hospital's red-cell stock with shortage levels, usable
units and near expiry, free beds, available equipment and rooms, active cases and open needs, plus network totals. The page
reads it every 60 seconds while open. Nothing on the page changes stock, beds, rooms, equipment or cases.

## Design

### Backend: new app `apps/command_centre` (no models)

- `services.py`: `network_figures(now=None) -> dict`. Seven grouped queries, one per dimension, whatever the number of
  hospitals: active hospitals, blood units (grouped by hospital, group and component), free beds, available equipment,
  available operating rooms, active cases, and open needs (quantity less fulfilled less held, per hospital and type, with
  the holds counted by a subquery). Rows are assembled in Python. Hospitals with a critical red-cell group are listed
  first, then the rest by name.
- `views.py`: `CommandCentreView`, `module_permission("commandCentre")`. Runs `escalate_overdue()` and `release_expired()`
  first (as the feed and the case pages do), then returns `network_figures()`.
- `urls.py`: `GET /api/command-centre/`, mounted in `config/urls.py`.
- Constants reused: `ACTIVE` plus `escalated` from `apps.emergencies.services` (the feed's set), `usable` = available and
  not expired (as `usable_units`), free beds, `matchable()` for equipment and rooms.

### Backend: red-cell minimums (`apps/blood/services.py`)

- `RED_CELL_MINIMUM` is a copy of `MINIMUM_STOCK.redCells` from `frontend/src/api/blood.ts`, with a comment pointing to it.
- `stock_level(count, minimum)`: `critical` below half the minimum, `low` below it, else `ok`. The same rule as `stockLevel`.

### Backend: access (`apps/accounts/permissions.py`)

- `"commandCentre": VIEW` on `Role.ADMIN` only. Frontend `roles.ts` gets the same row. `api-contracts.md` gets the column.

### Response shape (camelCase, counts and names only)

```
{
  updatedAt, nearExpiryDays,
  totals: { redCells: [{group, available}], components: {<c>: {usable, nearExpiry}}, beds: {<type>: n},
            equipment: {<type>: n}, operatingRooms: n, cases: {active, escalated}, open: {blood, bed, equipment, operatingRoom} },
  hospitals: [ { id, name,
                 redCells: [{group, available, minimum, level}],   // 8 groups, level ok|low|critical
                 components: {<c>: {usable, nearExpiry}}, beds, equipment, operatingRooms, cases, open } ]
}
```

Totals are sums of the hospital rows. A level is never worked out from a total.

### Frontend

- `src/api/commandCentre.ts`: types and `getCommandCentre()` (`GET /command-centre/`). Mocked in `src/test/mockApi.ts`.
- `src/features/commandCentre/commandCentre.ts`: pure helpers. Words for levels and near-expiry, the shortage summary,
  labels for bed types. Unit-tested.
- `src/features/commandCentre/useCommandCentre.ts`: loads, refreshes every 60 s, pauses while the tab is hidden (resumes with
  an immediate refresh), clears the timer and listener on unmount, keeps the last figures on a failed refresh.
- `src/features/commandCentre/CommandCentre.tsx` and `.module.css`: summary, four tables with a totals row.
- `src/pages/staff/CommandCentrePage.tsx`: the page, its loading, first-load failure (with Retry) and empty states.
- Routing: `App.tsx` route `command-centre`. `roles.ts`: `commandCentre` module, nav entry "City command centre",
  admin `view`. `planned.ts`: the `/staff/command-centre` line is removed.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Access row and copies of the rules: `commandCentre` in ACCESS, `RED_CELL_MINIMUM` and `stock_level` | `accounts/permissions.py`, `blood/services.py`, `roles.ts`, `api-contracts.md` (table) | `accounts/tests/test_permissions.py` (new endpoint row); `roles.test.ts` (table) |
| 2 | Aggregated service: seven grouped queries, levels, sorting, totals, open needs | `apps/command_centre/{__init__,apps,services}.py`, `config/settings.py` (INSTALLED_APPS) | `apps/command_centre/tests/test_figures.py` |
| 3 | Endpoint: sweeps first, admin only, mounted at `/api/command-centre/` | `apps/command_centre/{views,urls}.py`, `config/urls.py` | `apps/command_centre/tests/test_endpoint.py` (403s, sweeps, privacy keys) |
| 4 | Query budget: fixed count on the seeded network, unchanged when two hospitals are added, under one second | – | `apps/command_centre/tests/test_query_budget.py` |
| 5 | Frontend API, pure helpers, mock and fixtures | `src/api/commandCentre.ts`, `features/commandCentre/commandCentre.ts`, `test/fixtures/commandCentre.ts`, `test/mockApi.ts` | `commandCentre.test.ts`; red cells equal the Blood page's stock (backend test) |
| 6 | Page, refresh hook, nav, route, planned removal | `features/commandCentre/{useCommandCentre,CommandCentre}.tsx`, `.module.css`, `pages/staff/CommandCentrePage.tsx`, `App.tsx`, `roles.ts`, `planned.ts` | `CommandCentrePage.test.tsx` (words, order, alert, empty, error, 60 s refresh, hidden tab, unmount); `StaffLayout.test.tsx` and `roles.test.ts` (enumerations) |
| 7 | QA and docs | `qa/features.qa.test.tsx`, `docs/architecture/api.md`, `api-contracts.md` | QA test: admin nav has the link, nurse nav doesn't |

## Sequencing

1 → 2 → 3 → 4 (backend, each with its tests), then 5 → 6 → 7. Unit 1 goes first because the others use the access row.

## Test plan

- **Figures:** per hospital, the red-cell counts, usable and near-expiry units, free beds (reserved and cleaning don't count),
  available equipment and rooms (in use doesn't count), active cases and escalated, open needs (quantity less fulfilled less
  held, never below 0). Only usable units count: reserved, quarantined, issued and expired don't.
- **Shortage levels:** A− minimum 4 at 0, 1, 2, 3, 4 units gives critical, critical, low, low, ok, with the count and minimum.
- **Blood page agreement:** on the seeded network, each hospital's red-cell `available` and `nearExpiry` equal the
  `stock_summary` rows for that hospital (the Blood page's stock summary).
- **Totals:** each total equals the sum of the hospital rows.
- **Inactive hospitals:** a deactivated hospital with stock and cases is in neither the rows nor the totals.
- **Order:** hospitals with a critical red-cell group first, then by name.
- **Cases:** open, matching, partially fulfilled and escalated count as active; fulfilled, closed and cancelled don't.
- **Sweeps:** a critical case past the escalation window is escalated by the GET, and an expired hold is released first.
- **Privacy:** every key in the response is on an allow-list (no patient, case reference, unit or asset identifier, staff name).
- **Access:** admin 200; doctor, nurse, blood bank, pharmacist, patient and signed-out callers 403.
- **Query budget:** the service and the endpoint, on the seeded network, at most 15 queries; the count is identical after
  two active hospitals with stock and cases are added. Under one second.
- **Frontend:** the page renders the words for each level and near-expiry figure, with no colour-only status; "No shortages"
  for a clean hospital; the summary lists short groups; the 60-second refresh runs while visible and stops when hidden or
  unmounted; a failed refresh keeps the figures and shows `role="alert"`; a failed first load shows an error with Retry;
  an empty network says so.
- **CI:** the three check commands in `AGENTS.md`: ruff, makemigrations (no new migrations expected), pytest, npm lint,
  npm test, npm build, `check_deploy_config.py`, `aidlc_board.py --check`.

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that
approval is the Construction gate.
