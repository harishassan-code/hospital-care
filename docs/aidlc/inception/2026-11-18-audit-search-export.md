# Inception Spec: Audit search and export

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B10](../bolts/B10-audit-search-export.md)
**Related backlog item:** [#56 Audit search and export](https://github.com/harishassan-code/hospital-care/issues/56)
(Sprint 8; builds on the action log that the services already write, see
[API contracts: Audit](../../architecture/api-contracts.md#audit-story-81))

## Problem

Every critical action already writes an audit row through `apps.audit.services.record()`. Each row says who acted, on
what, when, and the values before and after. Only Django admin shows these rows. Admin can filter by action and target
type and search by email and target, but it has no date range and no export. It is also a separate Django page, not
part of the staff app.

This is for the administrator. An administrator needs to review what happened to a case, a unit or an account, and
hand that record to someone else.

## User stories

- As an administrator, I want to search the audit trail by actor, action, target and date range, so that I can find the
  actions I need to review. (#56)
- As an administrator, I want to export the search result to CSV, so that a review can be kept or shared outside the
  app. (#56)

## Acceptance criteria

### Access

- [ ] Two read-only endpoints: `GET /api/audit/entries/` (the search) and `GET /api/audit/entries/export/` (the CSV).
- [ ] Only the admin role can use them (`audit` module, view). Superusers act as admins. Every other role, and a
      signed-out user, gets 403.
- [ ] The **Audit log** link shows in the staff menu for admins only.
- [ ] Scope is the whole network. Audit rows have no hospital field, so there is no hospital filter.
- [ ] `ACCESS` in `backend/apps/accounts/permissions.py`, `ACCESS` in `frontend/src/features/staff/roles.ts` and the
      access table in `docs/architecture/api-contracts.md` change in the same PR.

### Search

- [ ] Filters are all optional and combine with AND:
  - [ ] `actor`: the account's email, matched exactly and ignoring case. It still matches after the account is deleted,
        because `actor_email` is kept.
  - [ ] `action`: starts-with match. `bed.` finds every bed action. `bed.status_changed` finds that one action.
  - [ ] `targetType`: exact match on `target_type`, such as `hospitals.hospital`.
  - [ ] `targetId`: exact match on `target_id`. Used with `targetType`, it shows one object's history.
  - [ ] `from` and `to`: dates as `YYYY-MM-DD`. Both ends are whole days in `Asia/Karachi` (the project's `TIME_ZONE`).
        `to=2026-11-18` includes everything on 18 November. A date that doesn't parse, or a `to` before `from`, gives 400.
  - [ ] `q`: case-insensitive text match on `actor_email`, `action`, `target_repr`, `target_id` and `reason`. It does not
        search `before` or `after`.
- [ ] Results are newest first: `at` descending, then `id` descending.
- [ ] Paging: `limit` (default 50, maximum 200) and `offset` (default 0). A value that isn't a whole number, or is
      negative, gives 400. A `limit` above 200 is cut to 200.
- [ ] The response is `{count, limit, offset, results}`. Each result has `id`, `at`, `actorEmail`, `action`, `targetType`,
      `targetId`, `targetRepr`, `reason`, `before` and `after`. Times are ISO 8601 in UTC.
- [ ] The page shows a table with **Previous**, **Next** and a count such as "1–50 of 1,234". Each row's `before` and
      `after` open on click and are shown as JSON text.

### Export

- [ ] `GET /api/audit/entries/export/` takes the same filters and returns a CSV file (`text/csv`, sent as an attachment).
      The file name is `audit-<export date>.csv`.
- [ ] Columns, in this order: `at`, `actorEmail`, `action`, `targetType`, `targetId`, `targetRepr`, `reason`, `before`,
      `after`. Times are in UTC. `before` and `after` are JSON text in one cell each.
- [ ] An export holds at most 10,000 rows. If the filters match more, the answer is 400 `{detail}` asking the user to
      narrow the filters, and no file is sent. A cut-off file is never sent.
- [ ] Rows are written in chunks as they are read. The whole result is not loaded into memory first.
- [ ] A cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a single quote in front, so a
      spreadsheet does not run it as a formula.
- [ ] A successful export writes one `audit.exported` record (see open question 1). A refused export writes none.
- [ ] The export page button downloads the file for the filters currently set. A 400 shows its message in the page's alert.

### Read only

- [ ] Both endpoints accept GET only. POST, PUT, PATCH and DELETE answer 405.
- [ ] The model still refuses updates and deletes (existing tests), and the Django admin stays read-only (existing test).
- [ ] No code path in the app updates or deletes an `AuditLog` row.

### Performance

- [ ] Each list page runs a fixed number of queries: one count and one select. There is no query per row. A test counts
      the queries.
- [ ] On PostgreSQL with 100,000 rows, the first page returns in under 1 second with a one-month date range. This is
      checked once on staging with generated rows. It is not a CI test.
- [ ] The date filter uses the existing index on `at`. MVP adds no new index. Free-text search scans the rows the other
      filters leave, which is fine at this size.

### Build and tests

- [ ] Filter and export rules live in `backend/apps/audit/services.py`. Views only read the query string and return the
      result.
- [ ] Each endpoint has a permission class and a backend test. The tests cover each filter, paging limits, 400 on bad
      input, the 10,000-row refusal, CSV escaping, 403 for other roles, 405 for writes and the `audit.exported` record.
- [ ] Frontend: calls go through `frontend/src/api/audit.ts`. `frontend/src/test/mockApi.ts` mocks them with the same
      shape. A test covers the filter form, paging and the export button.
- [ ] `/staff/audit` is removed from `frontend/src/features/staff/planned.ts`. The QA test checks the Audit link for admin
      with `arrayContaining` and checks it is absent for other roles with `not.toContain`.

## The rules in one place

| Thing | Rule |
|---|---|
| Who can see it | Admin only: `audit` module, view. Superusers act as admins. |
| Scope | The whole network. Audit rows have no hospital, so there is no hospital filter. |
| Actor | Exact, case-insensitive match on `actor_email`. |
| Action | Starts-with match on `action`. |
| Target | `target_type` exact. `target_id` exact, used with the type. |
| Dates | `from` and `to` are whole days in `Asia/Karachi`. Times are stored in UTC. |
| Free text | Contains, case-insensitive, over `actor_email`, `action`, `target_repr`, `target_id`, `reason`. Not `before` or `after`. |
| Order | Newest first: `at` descending, then `id` descending. |
| Paging | Default 50, maximum 200, on the search only. None of the current list endpoints page (`GET /api/hospitals/` returns every row), so this sets the shape. |
| Export | Same filters, CSV, UTC times, at most 10,000 rows. Over the cap: 400 and no file. |
| CSV safety | Cells starting with `= + - @`, a tab or a carriage return get a leading `'`. |
| Writes | None through the API. The model refuses updates and deletes. |
| Logging | Each successful export writes `audit.exported`. Page views and searches are not logged. |

## Non-goals

- Changing, deleting or "unallocating" audit rows. The model refuses both. A correction is a new action.
- Other export formats (PDF, Excel) and scheduled or emailed exports. Operational reports (B18) may reuse this export later.
- Searching inside `before` and `after` values.
- Logging every page view or search. Only exports are logged.
- Audit pages for roles other than admin, and per-hospital audit views.
- Saved searches, live refresh and charts.
- Retention or archiving of old rows. Nothing is deleted.
- Any change to the Django admin page.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Should exporting the audit log itself be audit-logged?** Proposed: yes. Each successful export writes
   `audit.exported` through `record()`. The target is the exporting admin's own account, since an export has no single
   object. The filters and row count go in `after`. Reason: an export takes the record out of the system, so reviewers
   need to know who took it.
2. **What is the export row cap?** Proposed: 10,000 rows. Above that the export is refused with 400, never cut short.
   Reason: a cut-off file looks complete, so a reviewer could miss rows without knowing.
3. **Should the actor filter match the email or the user id?** Proposed: the email (`actor_email`). Reason: the `actor`
   link is cleared when an account is deleted, but the email stays.
4. **Which timezone do the date filters use?** Proposed: `Asia/Karachi`, the project's `TIME_ZONE`, with stored times in
   UTC. Reason: staff think of a day in local time, so a day filter should match a calendar day.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
