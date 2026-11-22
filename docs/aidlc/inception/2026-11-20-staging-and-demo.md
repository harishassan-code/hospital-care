# Inception Spec: Staging deployment, demo data and demo script

**Date:** 2026-11-20
**Author:** Hassan Qureshi (Claude, drafted for review)
**Bolt:** [B14](../bolts/B14-staging-and-demo.md)
**Related backlog items:** #69 Set up staging deployment (Render + Vercel), #59 Final staging deployment and demo
data (Epic E0, Sprint 9)

## Problem

Every sprint review and the final demo should run from one live URL that anyone on the team, and the Product Owner,
can open. The config for it already exists (`render.yaml`, `frontend/vercel.json`, `seed_demo` in the Render build,
`scripts/check_deploy_config.py` in CI), but nothing says which URL is the real one, the README only names the hosts,
and there is no written demo script. Without a script, each demo depends on whoever is presenting remembering the
steps, and a demo can hit an empty list or a sleeping API in front of the instructor.

This is for the whole team (presenters), the Scrum Master (who owns the deployment) and the Product Owner (who reviews
the product on staging).

## User stories

- As the team, I want `main` deployed to a stable staging URL, so that every sprint review demos from a live site. (#69)
- As a presenter, I want staging seeded with the demo scenario and a written, rehearsed demo script, so that the final
  demo runs the same way every time. (#59)

## Acceptance criteria

- [ ] The Render blueprint is deployed from `main`; `GET <render-url>/api/health/` returns `{"status": "ok"}`.
- [ ] The Vercel project is deployed from `frontend/` with `VITE_API_URL=/api`; the home page shows **API status: up**.
- [ ] `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` on Render are set to the Vercel URL, and a signed-in change
      (for example, updating a bed) succeeds on staging, which proves the CSRF set-up end to end.
- [ ] The README has a **Staging** section with both URLs, the demo logins (already public in `deployment.md`) and a
      note that the API sleeps after 15 minutes idle. Both URLs are pinned in Discord `#links`.
- [ ] Staging holds the demo scenario from `seed_demo`: the demo hospitals, stock and one login per role.
- [ ] `docs/setup/demo-script.md` exists: who presents, what to open first, each step with the role to sign in as, the
      action and what the audience should see, timings that fit the demo slot, and a fallback for each step that can
      fail (sleeping API, expired holds, data already used up by a rehearsal).
- [ ] The script is rehearsed end to end on staging once, and the rehearsal date and any fixes are recorded at the end
      of the script.
- [ ] A small smoke check, `scripts/smoke_staging.py <vercel-url>`, checks the health endpoint through the Vercel
      proxy and the home page, so anyone can confirm staging is up before a demo (proposed in Q3).

## Design

- **No feature code.** Only docs, the README and one small script.
- **Deployment** follows [deployment.md](../../setup/deployment.md) as written. If Render gives the service a different
  host, `frontend/vercel.json`'s `/api` route changes with it, and `check_deploy_config.py` keeps the two in step.
- **Demo data:** the Render build already runs `seed_demo`, which only fills empty tables. To reset staging after a
  rehearsal, use `seed_demo --reset` from the Render shell (documented in the script, not run automatically).
- **Demo script** (`docs/setup/demo-script.md`) is built on the walkthrough in
  [authentication-test-report.md](../../testing/authentication-test-report.md). It follows the MVP path that is on
  `main`: sign in per role → emergency case → local availability and shortfall → ranked candidate hospitals → reserve
  → transfer request, approval, dispatch and delivery (B01–B03) → allocation and case status. Features still in open
  PRs (ambulances, alerts, dashboards, audit search, specialists, patient transfer) get a step only once they are
  merged, so the script never shows something staging doesn't have.
- **Smoke check:** standard-library Python (`urllib`), exit code 0/1, no new dependency, not run in CI (staging is
  outside CI's reach).

## Non-goals

- Feature work or fixes to features (bugs found in rehearsal become issues).
- A paid plan, a custom domain or production hosting.
- Automating the deployment beyond what Render and Vercel already do on every push to `main`.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Who owns the Render and Vercel accounts, so the URLs survive after the course?** *Proposed:* the repository owner
   (Haris Hassan, `harishassan-code`) creates both projects by signing in with GitHub, since both hosts deploy from the
   repo and need its owner's permission. No passwords are shared; teammates use the public URLs and the demo logins.
   The free Render Postgres expires 30 days after it is created, so the README records the creation date and a reminder
   to recreate it before the final demo.
2. **Who runs the deployment clicks?** *Proposed:* the account owner does the one-time set-up in `deployment.md`
   (about 15 minutes); Claude can't sign in to Render or Vercel. Everything else in this bolt (README, demo script,
   smoke check) is written in the repo and reviewed in the PR.
3. **Add the smoke-check script?** *Proposed:* yes. It is about 40 lines, needs nothing installed, and turns "open the
   site two minutes before the demo" into one command that also wakes the API.
4. **Which features go in the final demo?** *Proposed:* what is merged into `main` by the rehearsal. The script lists
   the optional steps for the open PRs (#104, #106–#110) and marks each one "include once merged".

## Approval

- [ ] Approved by: pending (Product Owner / Scrum Master, via PR review)
