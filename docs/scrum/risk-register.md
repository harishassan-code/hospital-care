# Risk register

WBS 1.1.3 (risk planning) and 1.4.2 .2 (update the risk register). Reviewed at sprint planning.
**Score** = likelihood (1–3) × impact (1–3). **Status** is as of 22 Nov 2026 (Sprint 8).

| # | Risk | L | I | Score | Mitigation | Owner | Status |
|---|---|---|---|---|---|---|---|
| R1 | Work is integrated in large batches instead of each sprint, so reviews have nothing on `main` to demo and conflicts pile up | 3 | 3 | 9 | Weekly integration PR (CONTRIBUTING §5); AIDLC bolts sized to one PR; CI on every push | Scrum Master | **Occurred** in Sprints 1–7 (two big integrations, 19 Oct and 17 Nov; see [timeline](timeline.md#velocity-check)). Bolts since Sprint 7 merge one by one |
| R2 | Two hospitals reserve the same unit, bed or ventilator at the same moment (double allocation) | 2 | 3 | 6 | Reservations in `transaction.atomic()` with `select_for_update()`; concurrency tests (#44) | Backend | Mitigated: tests run on PostgreSQL in CI |
| R3 | Real patient data ends up in the demo or the repository | 1 | 3 | 3 | Synthetic `seed_demo` only; patient fields limited to a tag and initials; rule in AGENTS.md and CONTRIBUTING | Everyone | Mitigated |
| R4 | Clinical rules (blood compatibility, donor eligibility) are taken as medical advice | 1 | 3 | 3 | Rules documented from an authoritative source (#6) and stated as simulated in the proposal, WBS and docs | Product Owner | Mitigated |
| R5 | Staging is down or asleep during the review (free Render plan sleeps after 15 minutes) | 3 | 2 | 6 | Wake it with `scripts/smoke_staging.py` 10 minutes before; local Docker as fallback ([demo script](../setup/demo-script.md)) | B14 owner | Open until the final demo |
| R6 | A late merge breaks `main` just before the demo | 2 | 3 | 6 | CI on every PR (lint, tests, build, e2e); no new features in Sprint 9 unless the e2e scenario is green | Scrum Master | Open. Flaky tests turned `main` red on 22 Nov (fixed in #115 and #120) |
| R7 | Candidate search too slow on a city-sized network | 2 | 2 | 4 | Query counts pinned by tests; `seed_demo --hospitals N` and the search load test (B13) | B13 owner | Mitigated: p95 26 ms (one user) and 108–139 ms (five at once) on PostgreSQL with 50 hospitals ([load test](../testing/search-load-test.md)). Recheck on staging once it is up |
| R8 | An endpoint ships without a role check | 2 | 3 | 6 | One access table in two places; a test that fails if any `/api/` view is open or only checks sign-in (#114) | Backend | Mitigated: the URL-walk test is on `main` (#114) and all 66 routes were reviewed ([security review](../testing/security-review.md)) |
| R9 | Scope larger than capacity (WBS 1,947 h for an 8-person student team) | 3 | 2 | 6 | Scope-cut order in the [timeline](timeline.md#scope-cut-order-if-velocity-is-lower-than-planned); ADV items only if velocity allows | Product Owner | Mitigated: MVP delivered, ADV items B16–B18 built; remaining WBS gaps listed in the [roadmap](../deliverables/handover-and-roadmap.md) |
| R10 | Uneven contribution, or a member unavailable (exams) | 2 | 2 | 4 | Availability table in [team.md](team.md); bolts have one owner; max 2 bolts in progress per person | Scrum Master | Open |
| R11 | AI-generated code merged without understanding | 2 | 2 | 4 | AIDLC gates: approved spec before code, reviewer approval before merge, owner credited as author | Everyone | Mitigated by process |
