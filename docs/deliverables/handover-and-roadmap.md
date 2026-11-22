# Handover note and future roadmap

WBS 10.3.3 .2 ("Write the handover note and future roadmap"). State as of 22 Nov 2026 (Sprint 8).

## 1. What is handed over

Hospital Care (CityCare): a city-wide platform where hospitals share blood, beds, equipment, operating rooms and
ambulances, so an emergency case can find, reserve and transfer what it needs.

| Area | Where | Notes |
|---|---|---|
| Backend | `backend/` (Django 6, DRF) | One app per module in `backend/apps/`; business rules in each app's `services.py` |
| Frontend | `frontend/` (React 19, TypeScript, Vite) | Pages in `src/pages/`, API calls only through `src/api/` |
| End-to-end test | `e2e/` (Playwright) | The MVP acceptance scenario; runs in CI on pull requests |
| Deployment | `render.yaml` (API + PostgreSQL), `frontend/vercel.json` | [Deployment guide](../setup/deployment.md), [demo script](../setup/demo-script.md) |
| CI | `.github/workflows/ci.yml` | Lint, migrations check, backend and frontend tests, build, deploy-config check, e2e |
| Demo data | `python manage.py seed_demo` | Synthetic only; one login per role, password `CityCare-demo-1` |

**Start here:** [README](../../README.md) (run it), [user manual](../setup/user-manual.md) (use it),
[architecture](../architecture/README.md) and [API contracts](../architecture/api-contracts.md) (change it),
[AGENTS.md](../../AGENTS.md) and [CONTRIBUTING.md](../../CONTRIBUTING.md) (the rules every change follows),
[bolt board](../aidlc/bolts/README.md) (what is done and in review).

## 2. Rules a new developer must keep

- Access control is one table in two places: `backend/apps/accounts/permissions.py` (enforced) and
  `frontend/src/features/staff/roles.ts` (hides UI). Change both, and `docs/architecture/api-contracts.md`.
- Every state change is audit-logged with `apps.audit.services.record` and goes through the resource's
  `StateMachine`. Anything that moves stock runs in `transaction.atomic()` with `select_for_update()`.
- Migrations already on `main` are never edited. Demo data stays synthetic.
- New work runs as an AIDLC bolt: an approved spec, then construction, then operations notes.

## 3. Open at handover

| Item | Owner / where |
|---|---|
| Staging deployment and demo rehearsal (B14) | Not deployed yet ([#69](https://github.com/harishassan-code/hospital-care/issues/69)); B14 owner, following the [deployment guide](../setup/deployment.md) |
| Final report and presentation (B15) | Done: [final report](final/final-report.md) and [slides](final/final-presentation.pptx). Add the Sprint 8 and 9 records after their ceremonies, and staging screenshots after B14 |
| Operations notes for the merged bolts (B01–B13, B16–B18) | Each bolt owner, once staging is live |
| Search p95 latency rechecked on staging (#58) | Measured on PostgreSQL: [load test](../testing/search-load-test.md); rerun the same command against staging |
| Product Owner UAT sign-off | [UAT checklist](../testing/uat-checklist.md) |

## 4. Future roadmap: WBS/FBS items not built

Checked against the code on `main` on 22 Nov 2026. These are in the WBS/FBS but were not in the team's
backlog, so they were never scheduled. Ordered by value for the next team.

| Priority | FBS ref | Item | State today |
|---|---|---|---|
| 1 | F1.2 .2 | Password reset flow | Not built (failed-login lockout exists) |
| 1 | F8.1 .2 | Email notifications | In-app only; add an `EmailChannel` next to the in-app one |
| 1 | F5.1 .2 .4, F5.2 .2 | Required-by time, numeric priority score, acceptable time window | Cases sort by severity, then age |
| 2 | F3.1 .2 .6 | Bed features (ventilator-ready, monitored); capacity thresholds with alerts | Not built |
| 2 | F7.2 .1 .2 .3 | Ambulance onboard equipment, driver and crew, auto-pick the nearest suitable ambulance | Manual pick with ETA exists |
| 2 | F8.2 .5 | City map of hospitals, capacity and emergencies | Command centre is a table |
| 2 | F3.3 .2 .3 .5 | OR turnaround time, rescheduling, next free emergency slot | Booking and clash prevention exist |
| 3 | F4.1 .2 .6 | Donor consent and contact preferences, emergency donor call-out | Not built |
| 3 | F4.2 .8 | Wastage reason *codes* | Free-text reason today |
| 3 | F3.2 .2 | Equipment transferable / fixed flag | Not built |
| 3 | F2.1 .2 | Hospital approval workflow (approve, suspend) | Active / inactive flag only |
| 3 | F5.3 .1 | Draft state for requests | Cases start at Open |
| 3 | F6.1 .5 | Caching of distance / search results | Only blood rules are cached |
| 3 | F7.1 .4 | Explicit hand-over and receipt record | Each step's actor is in the transfer history |

Also worth doing: move the request-time sweeps (hold expiry, escalation) to a scheduled job, as their `ponytail:`
notes in the code describe.
