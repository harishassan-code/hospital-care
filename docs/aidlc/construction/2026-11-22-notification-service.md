# Construction Plan: Notification service

**Spec:** [docs/aidlc/inception/2026-11-22-notification-service.md](../inception/2026-11-22-notification-service.md)
**Bolt:** [B06](../bolts/)
**Date:** 2026-11-22

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Notification + receipt models, `notify` with Channel abstraction | `apps/notifications/models.py`, `services.py`, `admin.py`, migration | a failing channel never breaks the action |
| 2 | Events wired next to the audit records | `apps/transfers/services.py`, `apps/emergencies/services.py`, `apps/matching/reservations.py` | transfer request reaches the supplier's answering role as critical; approval tells the receiver |
| 3 | List / unread count / read / read-all / acknowledge API | `apps/notifications/views.py`, `urls.py`, `config/urls.py` | per-user read state; patients 403; other hospital 404 |

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
