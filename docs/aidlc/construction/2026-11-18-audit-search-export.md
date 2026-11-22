# Construction Plan: Audit search and export

**Spec:** [docs/aidlc/inception/2026-11-18-audit-search-export.md](../inception/2026-11-18-audit-search-export.md)
**Date:** 2026-11-18

B10 is one bolt with one read-only API and one page. It adds no model change and no index: the date filter uses the
existing `at` index (spec, Performance). The four proposed answers in the spec (admin only, 10,000-row cap, email
matching, `Asia/Karachi` days) are built as proposed.

## Design

### Backend (`backend/apps/audit/`)

- **Access.** `"audit": VIEW` in `ACCESS` for `admin` only (`accounts/permissions.py`). Superusers already act as admins.
- **Routes.** `config/urls.py` mounts `apps.audit.urls` at `/api/audit/`: `entries/` (search) and `entries/export/` (CSV).
  No route at `/api/audit/` itself, so the existing "no API to change entries" test still holds.
- **Read-only views.** Both views accept GET (and HEAD, OPTIONS). Every other method answers 405 before the access check,
  for any caller, so a write is never mistaken for a permission problem.
- **Services (`services.py`).** All rules live here:
  - `filters_from(params)`: parses `actor`, `action`, `targetType`, `targetId`, `from`, `to`, `q`. Blank means not set.
    A bad date, or `to` before `from`, raises `AuditQueryError` (400).
  - `paging_from(params)`: `limit` (default 50, capped at 200) and `offset` (default 0). Non-whole or negative values raise
    `AuditQueryError`.
  - `apply_filters(qs, filters)`: `actor_email__iexact`, `action__startswith`, `target_type`, `target_id`, `at` between
    the Karachi midnights (UTC bounds), `q` as an OR of `icontains` over five fields. Ordered `-at, -id`.
  - `search(params)`: one count and one sliced select.
  - `export_query(params)`: the same filters. Refuses with 400 when the count is over `MAX_EXPORT_ROWS` (10,000).
  - `export_chunks(qs, actor, filters)`: the generator behind the file. Writes the header, then batches of 500 rows
    through the csv module. Cells that start with `= + - @ TAB CR` get a leading `'`. On success it writes one
    `audit.exported` record through `record(actor, ..., actor, after={filters, rows})`. The record is written when the
    last chunk has been read, so an export that is cut short writes none.
- **Exception.** `AuditQueryError` subclasses DRF's `APIException` with status 400, so DRF renders `{"detail": "..."}`.
- **Serializer (`serializers.py`).** `AuditEntrySerializer`: camelCase fields, `at` in UTC (`default_timezone=utc`). The CSV
  reuses it, so the JSON and the file agree on every value.
- **Access check.** `module_permission("audit")` from `accounts/permissions.py`, the same class as every other module.

### Frontend (`frontend/src/`)

- `api/client.ts`: `apiDownload(path)` returns `{blob, filename}` from `Content-Disposition`. A failure reads its JSON
  body like the other calls, so a 400 shows its `detail`.
- `api/audit.ts`: types (`AuditEntry`, `AuditPage`, `AuditFilters`), `auditQuery()` (drops blank filters),
  `listAuditEntries()`, `exportAuditCsv()`, `AUDIT_PAGE_SIZE = 50`.
- `lib/download.ts`: `saveFile(blob, name)`. Creates an object URL and clicks a temporary link.
- `features/staff/roles.ts`: `audit` in `Module`, nav entry **Audit log** at `/staff/audit` (after Users), ACCESS admin view
  only. Identical to the backend.
- `features/staff/planned.ts`: `/staff/audit` removed. `App.tsx`: real route `audit` → `AuditPage`.
- `pages/staff/AuditPage.tsx`: filter form (actor, action, object type, object id, from, to, text) with Search and Clear;
  results table (When, Who, Action, Object, Reason, Details); a Details button opens `before` and `after` as JSON text;
  Previous/Next with "1–50 of 1,234"; **Export CSV** downloads for the filters that produced the table on screen.
- `test/mockApi.ts` + `test/fixtures/audit.ts`: `GET /audit/entries/` and `GET /audit/entries/export/`, behaving like the
  server (same filters, paging, newest first, 400 over the cap). `Reply` gains an optional `file` for non-JSON bodies.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Access row, search service, serializer, list view, routes | `apps/accounts/permissions.py`, `apps/audit/{services,serializers,views,urls}.py`, `config/urls.py` | `apps/audit/tests/test_search_api.py` |
| 2 | CSV export: cap, escaping, streaming, `audit.exported` | `apps/audit/{services,views}.py` | `apps/audit/tests/test_export_api.py` |
| 3 | Frontend API, download helper, role row, route, mocks | `src/api/{client,audit}.ts`, `src/lib/download.ts`, `src/features/staff/{roles,planned}.ts`, `src/App.tsx`, `src/test/{mockApi.ts,fixtures/audit.ts}` | `roles.test.ts`, `App.test.tsx` |
| 4 | Audit page | `src/pages/staff/AuditPage.tsx`, `AuditPage.module.css` | `src/pages/staff/AuditPage.test.tsx` |
| 5 | QA and docs | `src/qa/features.qa.test.tsx`, `docs/architecture/api.md`, `docs/architecture/api-contracts.md` | QA test; ruff, pytest, vitest, build |

## Sequencing

1 → 2 (both touch the same service module) → 3 → 4 → 5. Backend first, so the mock in unit 3 copies the real shape.

## Test plan

- **Search:** each filter alone and combined with AND; actor matched case-insensitively and still after the account is
  deleted; `action` starts-with; `targetType` and `targetId` together; `from`/`to` whole Karachi days at both edges;
  `q` over the five fields and not over `before`/`after`; bad dates, `to` before `from` → 400; newest first with ties by id.
- **Paging:** default 50; `offset` walks the set; `limit` 500 → 200; non-numbers and negatives → 400; a fixed query count
  (one count, one select) at 1 row and at 60 rows.
- **Export:** header and column order; UTC times; `before`/`after` as JSON text; filters apply; `text/csv` attachment with
  `audit-<date>.csv`; formula escaping for each of the six starting characters; 10,001 matching rows → 400 with `detail`
  and no file; `audit.exported` written only after the file is read to the end, with filters and row count; 403 for
  other roles and anonymous; 405 for POST, PUT, PATCH, DELETE.
- **Access:** 403 for doctor, nurse, blood bank, pharmacist, patient and signed-out; superuser allowed.
- **Frontend:** filter form sends the query; paging buttons; details open; export downloads with the server's file name;
  a 400 shows its message in the alert; nav shows Audit log for admin only (QA test with `arrayContaining` /
  `not.toContain`).
- **CI checks:** the three command groups in `AGENTS.md`: ruff check and format, `makemigrations --check` (no migration
  expected), pytest; `npm run lint`, `npm test`, `npm run build`; `check_deploy_config.py` and `aidlc_board.py --check`.
- **Not in CI:** the 100,000-row, under-one-second check on PostgreSQL in staging (spec, Performance).

## Review

Each unit's PR requires reviewer approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md) before merge — that approval is
the Construction gate.
