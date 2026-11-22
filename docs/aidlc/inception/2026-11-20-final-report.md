# Inception Spec: Final report and demo presentation

**Date:** 2026-11-20
**Author:** Hassan Qureshi (Claude, drafted for review)
**Bolt:** [B15](../bolts/B15-final-report.md)
**Related backlog item:** #60 Final report and demo presentation (Epic E0, Sprint 9)

## Problem

The course grades both the product and the process. The evidence is spread over the repository: sprint records in
`docs/deliverables/`, the velocity table in `docs/scrum/timeline.md`, AIDLC specs and plans in `docs/aidlc/`, test
reports in `docs/testing/` and the merged PRs. The instructor needs one report that tells the whole story and links to
that evidence, plus slides for the final demo.

This is for the Product Owner (the course instructor) and the team presenting the final demo.

## User stories

- As the team, I want a final report covering the process and the product, with velocity and burndown history and
  demo slides, so that the course can assess what we built and how. (#60)

## Acceptance criteria

- [x] `docs/deliverables/final/final-report.md` exists, with a PDF export next to it, and covers (screenshots are from
      a local run of the seeded app until staging is deployed, #69):
  - **Product:** the problem, the roles, what shipped (module by module, with the issues and PRs), the architecture
    (link to `docs/architecture/`), screenshots from staging, and what was not built (stretch items) and why.
  - **Process:** the team and roles, Scrum set-up (sprints, ceremonies, working agreement, DoR/DoD), the AIDLC bolt
    process with its gates, and an honest account of where the plan and the delivery differed (for example, Sprints
    5–7 landing together in #100).
  - **Quality:** test reports, CI checks and the E2E scenario (once B12 is merged).
  - **Lessons learned** from the retrospectives.
- [ ] Every sprint review and retrospective (Sprints 1–9) is linked from the report. *Sprints 1–7 are linked; the
      report has rows for 8 and 9, to fill in after those ceremonies (27 Nov and 4 Dec).*
- [x] A velocity chart (planned vs completed points per sprint) and a burndown chart are included as images in
      `docs/deliverables/final/charts/`, with the numbers they are drawn from.
- [x] Demo slides are in `docs/deliverables/final/` and follow the demo script from B14.
- [x] The deliverables index (`docs/deliverables/README.md`) marks the final report and presentation done.

## Design

- **No code** apart from one small chart script: `scripts/velocity_charts.py` reads the velocity table in
  `docs/scrum/timeline.md` and writes `velocity.png`; the burndown is drawn from closed-issue dates per sprint
  milestone, fetched once with the GitHub REST API and saved as CSV next to the chart, so the chart can be rebuilt.
- The report links to evidence instead of copying it, so it stays short (target 10–15 pages as PDF).

## Non-goals

- Writing the missing sprint records themselves: that is [B00](../bolts/B00-scrum-records-catch-up.md).
- New features or fixes.

## Dependency

This bolt **depends on B00**, which is still Ready and unassigned. Sprints 2–7 have no review or retrospective files
and the velocity table's *Completed* column is empty, so the two acceptance criteria from #60 can't be met until B00
is done. *Proposed:* write the report's product, architecture, AIDLC and quality sections now, and fill in the process
history, links and charts once B00 lands. The bolt stays in Backlog until then.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **What report format does the course require (PDF? template?)** *Proposed:* Markdown in the repo, exported to PDF,
   the same way as the authentication test report (`.md` + `.pdf`). If the course has a template, the PDF follows it.
2. **What format for the slides?** *Proposed:* a PowerPoint file (`final-presentation.pptx`), about 12 slides: problem,
   team and process, architecture, live demo (from the script), velocity and burndown, lessons learned, Q&A.
3. **Where does burndown data come from?** *Proposed:* closed-issue dates per sprint milestone via the GitHub REST API,
   plus the GitHub Project Insights screenshots the Scrum Master takes each Friday, if they exist.
4. **Who presents which part?** *Proposed:* each member presents the modules they built; the Scrum Master presents the
   process section. To be confirmed at the B14 rehearsal.

## Approval

- [x] Approved by: Hassan Qureshi (Hassan27521) on 2026-11-20, all proposed answers accepted
