---
id: B10
title: Audit search and export
issues: 56
points: 3
priority: medium
sprint: 8
depends_on: -
owner: codewithalphadotcom
status: In Review
---

# B10 · Audit search and export

**Goal:** Administrators search the audit trail and export it to CSV.

## Stories and acceptance criteria

[#56](https://github.com/harishassan-code/hospital-care/issues/56): As an administrator, I want to search and export the audit trail so that actions can be reviewed.

- [ ] Filter by actor, action type, entity and date range
- [ ] Export to CSV

## Build on

- `apps.audit.models.AuditLog` (`at`, `actor_email`, `action`, `target_type`, `target_id`, `target_repr`, `before`,
  `after`, `reason`) is written everywhere already; `apps/audit/views.py` is empty.
- Paginated list views elsewhere (e.g. `apps/hospitals/views.py`) for the filter/pagination style.
- Remove `/staff/audit` from `planned.ts` when the page lands.

## Scope

- **In:** Filtered, paginated read-only API (admin only), streamed CSV export, audit page.
- **Out:** Editing or deleting audit rows (the model refuses both, by design).

## Open questions for Inception

- Should exporting the audit log itself be audit-logged? (Recommended: yes.)

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-audit-search-export.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-audit-search-export.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-audit-search-export.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
