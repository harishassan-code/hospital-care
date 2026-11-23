---
id: B14
title: Staging deployment, demo data and demo script
issues: 59, 69
points: 3
priority: highest
sprint: 9
depends_on: -
owner: Hassan27521
status: In Progress
---

# B14 · Staging deployment, demo data and demo script

**Goal:** A stable staging URL anyone can open, seeded with the demo scenario, plus a rehearsed demo script.

## Stories and acceptance criteria

[#69](https://github.com/harishassan-code/hospital-care/issues/69) and [#59](https://github.com/harishassan-code/hospital-care/issues/59):

- [ ] Vercel project deployed from `main` (site + API, `vercel.json`); `<site>/api/health/` returns `{"status": "ok"}`
- [ ] Neon database connected from the Storage tab; a signed-in change works on staging
- [ ] The URL in the README and pinned in Discord `#links`
- [ ] Staging seeded with the demo scenario (`seed_demo`)
- [ ] Demo script written (`docs/setup/demo-script.md`) and rehearsed end to end

## Build on

- [docs/setup/deployment.md](../../setup/deployment.md), `vercel.json`, `backend/vercel_build.sh`;
  `scripts/check_deploy_config.py` guards the routing. (Render was dropped on 23 Nov: see the spec's amendment.)
- The walkthrough in [docs/testing/authentication-test-report.md](../../testing/authentication-test-report.md) is a good start for the demo script.

## Scope

- **In:** Deploy, seed, document URLs, demo script.
- **Out:** Feature work.

## Open questions for Inception

- Who owns the Vercel account, so the URL survives after the course?

## Exit checklist

- [ ] Everything under **Stories and acceptance criteria** is ticked, with links to the evidence
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
