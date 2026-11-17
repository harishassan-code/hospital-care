---
id: B00
title: Scrum records catch-up before the preliminary review
issues: 2
points: 2
priority: highest
sprint: 7
depends_on: -
owner: unassigned
status: Ready
---

# B00 · Scrum records catch-up before the preliminary review

**Goal:** Bring the course deliverables in line with the work that has shipped, so the instructor's preliminary review sees the process as clearly as the product. No code.

## Stories and acceptance criteria

From [#2](https://github.com/harishassan-code/hospital-care/issues/2) and the [Friday checklist](../../deliverables/README.md#friday-checklist-scrum-master):

- [ ] Every member has a row in [docs/scrum/team.md](../../scrum/team.md) (name, roll no., GitHub, focus area) via their own PR (#2)
- [ ] `docs/deliverables/sprint-02/` … `sprint-07/` exist with planning, review and retrospective, from the
      [templates](../../deliverables/templates/). Use the merged PRs, closed issues and the board history as evidence;
      write what actually happened, including what slipped.
- [ ] Sprint 1 review and retrospective filled in (both are still ⏳ in the index)
- [ ] Velocity table in [docs/scrum/timeline.md](../../scrum/timeline.md#velocity-check) filled in for sprints 1–7
- [x] Delivered issues closed after a check against their acceptance criteria: #26, #30, #32 and #37–#46
      shipped in #100 and were closed on 17 Nov with a comment linking the evidence
- [ ] [docs/deliverables/README.md](../../deliverables/README.md) index updated (sprint rows, Architecture/Wireframes status)

## Build on

- Merged PRs on GitHub (each lists its stories), `git log --merges origin/main`
- `docs/aidlc/inception/` and `construction/`: one spec and plan per Sprint 5–7 story, useful for review notes
- The GitHub Project board's Insights tab for burndown screenshots

## Scope

- **In:** Process records for sprints 1–7, team roster, closing delivered issues.
- **Out:** Any code change. The final report itself is B15.

## Open questions for Inception

- Who presents which sprint in the review? (Each person writes the review for the sprints they led.)
- Sprints where the plan and the delivered work differ a lot (Sprint 5–7 landed together in #100): record that
  honestly as a retro item rather than smoothing it over.

## Exit checklist

- [ ] Everything under **Stories and acceptance criteria** is ticked, with links to the evidence
- [ ] `status: Done` here, board regenerated (`python3 scripts/aidlc_board.py`), issue(s) closed
