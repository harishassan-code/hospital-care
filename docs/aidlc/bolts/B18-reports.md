---
id: B18
title: Operational reports and export
issues: 66, 67
points: 5
priority: low
sprint: stretch
depends_on: B10
owner: unassigned
status: Backlog
---

# B18 · Operational reports and export

**Goal:** Management can see historical reports (requests, fulfilment time, wastage) for a date range and export them.

## Stories and acceptance criteria

[#66](https://github.com/harishassan-code/hospital-care/issues/66), [#67](https://github.com/harishassan-code/hospital-care/issues/67):

- [ ] Reports for a selectable date range
- [ ] CSV and PDF export

## Build on

- `RequestStatusChange` (time to fulfil), `Allocation`, expired blood units (`expire_blood_units` command) and the
  audit log hold all the raw data. B10's CSV export pattern covers half of #67.

## Scope

- **In:** Report queries, page, CSV/PDF export.
- **Out:** Charts beyond simple tables.

## Open questions for Inception

- PDF library (WeasyPrint needs system packages on Render; a print stylesheet may be enough).

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-reports.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-reports.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-reports.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
