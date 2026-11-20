# Construction Plan: Staging deployment, demo data and demo script

**Spec:** [docs/aidlc/inception/2026-11-20-staging-and-demo.md](../inception/2026-11-20-staging-and-demo.md)
**Date:** 2026-11-20

No feature code. Two units are in the repo; one is done by the account owner on Render and Vercel.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Smoke check: health through the Vercel proxy, the API directly and the home page; exit 0/1 | `scripts/smoke_staging.py` | Run against a local `runserver` + `vite preview` and against a dead URL (must fail) |
| 2 | Demo script and README **Staging** section (URLs, logins, sleep warning, database expiry reminder) | `docs/setup/demo-script.md`, `README.md`, `docs/setup/deployment.md` (link to the script) | Review; rehearsal on staging |
| 3 | *(account owner)* One-time Render + Vercel set-up from `deployment.md`, set CORS/CSRF origins, fill the two URLs and the database creation date into the README, pin them in Discord | Render, Vercel, `README.md` | `python3 scripts/smoke_staging.py <vercel-url>` passes; a signed-in change works |
| 4 | Rehearse the script on staging; record the date and fixes at its end | `docs/setup/demo-script.md` | The rehearsal itself |

## Sequencing

1 and 2 now, on `hassanqureshi/b14-b15-b18`. 3 needs the account owner (Haris). 4 needs 3, and is best done after the
Sprint 8 PRs (#104) are merged, so the optional demo steps can be switched on.

## Test plan

CI checks from AGENTS.md stay green (`check_deploy_config.py` in particular). On staging: the smoke check passes, the
home page shows **API status: up**, and the demo script runs start to finish without a fallback.

## Review

The PR needs a reviewer's approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md).
