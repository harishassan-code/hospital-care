# Construction Plan: Final report and demo presentation

**Spec:** [docs/aidlc/inception/2026-11-20-final-report.md](../inception/2026-11-20-final-report.md)
**Date:** 2026-11-22

No feature code. The report links to evidence instead of copying it.

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | Velocity row for Sprint 8, as of 22 Nov (the sprint runs to 27 Nov), in the table B00 filled in | `docs/scrum/timeline.md` | The chart script parses it (unit 2) |
| 2 | Chart script: velocity from the timeline table; burndown from a one-time GitHub snapshot of every issue's milestone, points and close date, saved as CSV so the charts rebuild offline. Colours from the dataviz reference palette (validated for colour-vision deficiency), value labels on every bar | `scripts/velocity_charts.py`, `docs/deliverables/final/charts/` (`issues.csv`, `velocity.*`, `burndown.*`) | Run it; check both PNGs by eye for collisions and clipping; `ruff check` and `ruff format --check` with the backend's config |
| 3 | Screenshots of the seeded app: landing page, overview, a critical case and its ranked sources, transfers, command centre, audit log, reports. **Local run, not staging** (staging isn't deployed yet, #69); replace with staging shots after B14 | `docs/deliverables/final/screenshots/` | Taken after a full MVP scenario run, so they show real data |
| 4 | The report: product (problem, roles, what shipped by module with issues and PRs, architecture, screenshots, what wasn't built), process (team, Scrum, AIDLC gates, where plan and delivery differed), quality (tests, CI, E2E, load test, security review), lessons learned, sprint records | `docs/deliverables/final/final-report.md` | Every link resolves (checked by script); numbers match their sources |
| 5 | PDF export of the report: pandoc turns the Markdown (GitHub flavour) into HTML, and the same Chromium the E2E job uses prints it to A4. Links to other files in the repo point at GitHub, so they work outside the checkout | `docs/deliverables/final/final-report.pdf` | Open it; images and tables present (8 pages, 10 images) |
| 6 | Demo slides following the demo script (B14): 14 slides in the app's colours, a native (editable) velocity chart, two screenshots, speaker notes on each slide | `docs/deliverables/final/final-presentation.pptx` | Render each slide to an image and check for overflow; numbers match the report |
| 7 | Deliverables index: final report and presentation marked done | `docs/deliverables/README.md` | `scripts/aidlc_board.py --check` |

## Sequencing

1 before 2 (the script reads the table). 2 and 3 before 4 (the report embeds them). 4 before 5 and 6.

## Test plan

Links checked by script; charts and slides checked by eye. The repo's CI checks stay green: nothing here changes
code that CI tests, except that `scripts/velocity_charts.py` is linted with the backend's ruff config.

## Gaps against the spec (recorded, not hidden)

- **Sprint 8 and 9 reviews and retrospectives** don't exist yet: Sprint 8 ends 27 Nov, Sprint 9 on 4 Dec. The report
  links Sprints 1–7 and has rows for 8 and 9 to fill in after those ceremonies.
- **Screenshots are from a local run**, not staging (unit 3). The same set-up was rehearsed locally with staging's
  production settings, and the whole MVP scenario passed ([rehearsal](../../testing/mvp-scenario.md#against-production-settings-staging-rehearsal-22-nov)).
- **Lessons learned:** the Sprint 1–7 retrospectives were reconstructed from GitHub by B00 and record one lesson
  each. The report adds lessons from the record itself (the two big integrations, duplicate work, squash merges and
  credit, flaky tests), marked as such, for the team to confirm at the Sprint 8 retrospective.

## Review

The PR needs a reviewer's approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md).
