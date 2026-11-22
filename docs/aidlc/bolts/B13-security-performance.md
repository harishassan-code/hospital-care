---
id: B13
title: Security and performance hardening
issues: 58
points: 3
priority: high
sprint: 9
depends_on: -
owner: unassigned
status: Ready
---

# B13 · Security and performance hardening

**Goal:** Staging passes Django's deployment checks and the candidate search has a measured p95 latency on a city-sized dataset.

## Stories and acceptance criteria

[#58](https://github.com/harishassan-code/hospital-care/issues/58): Review permissions, run Django deployment checks, and load-test the search on a synthetic city-sized dataset.

- [ ] `manage.py check --deploy` clean on staging
- [ ] Search p95 latency recorded in the final report

## Build on

- Local `check --deploy` (with DEBUG off) currently warns about `SECURE_HSTS_SECONDS` and `SECURE_SSL_REDIRECT`.
  Secure cookies are already on when `DJANGO_DEBUG=false` (`backend/config/settings.py`); the secret key and DEBUG come from Render's env.
- `seed_demo` for a scaled-up dataset (add a `--hospitals N` option); `apps/matching/tests/test_candidates_performance.py`
  already pins query counts.
- Role table: `apps/accounts/permissions.py`; every view should use it. List any view that doesn't.

## Scope

- **In:** Deploy-check fixes, permission review notes, load test script + results.
- **Out:** New features.

## Open questions for Inception

- Load-test tool: `locust` or a simple Python timing script against staging?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-security-performance.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-security-performance.md` written
- [ ] Code, tests and docs merged; CI green; [Definition of Done](../../scrum/working-agreement.md) met
- [ ] Operations notes `docs/aidlc/operations/<date>-security-performance.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
