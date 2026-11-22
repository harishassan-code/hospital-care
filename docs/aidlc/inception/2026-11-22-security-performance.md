# Inception Spec: Security and performance hardening

**Date:** 2026-11-22
**Author:** Kabir-Raj-01, drafted with Claude
**Bolt:** [B13](../bolts/B13-security-performance.md)
**Related backlog item:** #58

## Problem

`check --deploy` still warns, nobody has confirmed that every view uses the role table, and the candidate search has
no measured latency on a realistic dataset.

## User stories

- As the team, we want staging hardened and the search measured, so that the final report can state both. (#58)

## Acceptance criteria

- [ ] With `DJANGO_DEBUG=false`, `manage.py check --deploy` has no warnings: `SECURE_SSL_REDIRECT`,
      `SECURE_HSTS_SECONDS` (with subdomains) and `SECURE_PROXY_SSL_HEADER` for Render, all controlled by env so local
      development is unaffected. A test runs the check with production-like settings.
- [ ] A test walks every URL pattern and fails if a DRF view has no explicit permission class, except an allow-list
      (health, login, signup, public landing data).
- [ ] `docs/testing/security-review.md`: permission review table (endpoint → permission class → own-hospital rule).
- [ ] `seed_demo --hospitals N` scales the synthetic city (the default of 3 keeps today's data).
- [ ] `scripts/load_test_search.py`: a plain Python timing script (stdlib `urllib` + `statistics`) that sends N
      requests to the candidates endpoint and prints p50/p95/max. Results for 50 hospitals go in
      `docs/testing/performance-report.md`.

## Non-goals

- New features. Penetration testing. Caching layers, unless p95 is over 500 ms.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Locust or a simple script?** Proposed: a simple stdlib script; no new dependency, and it runs anywhere.
2. **p95 target?** Proposed: under 500 ms at 50 hospitals on staging.

## Approval

- [x] Approved by: Kabir-Raj-01 (for the Product Owner) on 2026-11-22
