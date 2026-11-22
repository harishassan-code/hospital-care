# Inception Spec: Audit search and export

**Date:** 2026-11-22
**Author:** Kabir-Raj-01, drafted with Claude
**Bolt:** [B10](../bolts/B10-audit-search-export.md)
**Related backlog item:** #56

## Problem

Every state change is written to `AuditLog`, but there is no way to read it outside Django admin.

## User stories

- As an administrator, I want to search and export the audit trail, so that actions can be reviewed. (#56)

## Acceptance criteria

- [ ] `GET /api/audit/` (admin only), newest first, paginated, with filters: `actor` (email contains), `action` (exact,
      or a prefix ending in `.` such as `transfer.`), `target_type`, `target_id`, `from` / `to` dates (inclusive), and
      `q` (free text on target and reason).
- [ ] `GET /api/audit/export.csv` with the same filters streams CSV (`StreamingHttpResponse`). Columns: at,
      actor_email, action, target_type, target_id, target_repr, reason, before, after (JSON).
- [ ] Exporting is itself audit-logged (`audit.exported`, with the filters in `after`).
- [ ] Read-only: no create, update or delete endpoints.
- [ ] `/staff/audit` page: filter bar, table with expandable before/after, "Export CSV" button; placeholder removed.
      New `audit` module: admin view only (both access tables + docs).

## Non-goals

- Editing or deleting audit rows. Retention policies.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Audit the export?** Proposed: yes.
2. **Row limit on export?** Proposed: none; it is streamed.

## Approval

- [x] Approved by: Kabir-Raj-01 (author) on 2026-11-22 · Product Owner sign-off: pending
