# Course Deliverables

Everything the ASPM course can grade, in one place. The Scrum Master keeps this index current.
Each sprint gets a folder `sprint-NN/` built from the [templates](templates/).

## Project-level artefacts

| Artefact | Location | Status |
|---|---|---|
| Project proposal | [product/source/CityCare_Project_Proposal.docx](../product/source/CityCare_Project_Proposal.docx) | ✅ Submitted |
| Feature breakdown structure (WBS) | [product/source/ASPM Project FBS k232001.pdf](../product/source/ASPM%20Project%20FBS%20k232001.pdf) | ✅ Done |
| Product backlog (initial) | [product/backlog.md](../product/backlog.md) + GitHub Project | ✅ Done |
| Release plan / timeline | [scrum/timeline.md](../scrum/timeline.md) | ✅ Done |
| Working agreement, DoR, DoD | [scrum/working-agreement.md](../scrum/working-agreement.md) | ✅ Done |
| Architecture & ERD | [architecture/](../architecture/README.md) | ✅ Done (#3, closed 19 Oct) |
| UI wireframes | [architecture/](../architecture/README.md) | ✅ Done (#4, closed 19 Oct) |
| Test report: Authentication & Role-Based Access module (class assignment) | [testing/authentication-test-report.md](../testing/authentication-test-report.md) | ✅ Done |
| AIDLC process (Inception/Construction/Operations + templates) | [aidlc/](../aidlc/README.md) | ✅ Done |
| AIDLC bolt board (remaining work, Sprints 7–9) | [aidlc/bolts/](../aidlc/bolts/README.md) | ⏳ Ongoing |
| Velocity & burndown history | [scrum/timeline.md#velocity-check](../scrum/timeline.md#velocity-check) + per-sprint review; charts in [final/charts/](final/charts/) (`scripts/velocity_charts.py`) | ✅ Sprints 1–7 (B00); Sprint 8 as of 22 Nov (B15) |
| Final report & presentation | [final/final-report.md](final/final-report.md) ([PDF](final/final-report.pdf)), [final/final-presentation.pptx](final/final-presentation.pptx) | ✅ Done (B15). Add the Sprint 8–9 records and staging screenshots when they exist |

## Per-sprint artefacts

Created during the Friday ceremonies. Sprints 1–7 were reconstructed from the GitHub record by bolt B00 (#2); each
file marks what the team still has to confirm (attendance, Product Owner feedback, mood). Sprint 8's planning was
reconstructed the same way on 23 Nov, and its review and retrospective were prepared with the facts so far; the
team fills in the rest at the 27 Nov ceremonies.

| Sprint | Planning | Review | Retrospective | Burndown |
|---|---|---|---|---|
| 1 | [✅](sprint-01/sprint-planning.md) | [✅](sprint-01/sprint-review.md) | [✅](sprint-01/retrospective.md) | not captured |
| 2 | [✅](sprint-02/sprint-planning.md) | [✅](sprint-02/sprint-review.md) | [✅](sprint-02/retrospective.md) | not captured |
| 3 | [✅](sprint-03/sprint-planning.md) | [✅](sprint-03/sprint-review.md) | [✅](sprint-03/retrospective.md) | not captured |
| 4 | [✅](sprint-04/sprint-planning.md) | [✅](sprint-04/sprint-review.md) | [✅](sprint-04/retrospective.md) | not captured |
| 5 | [✅](sprint-05/sprint-planning.md) | [✅](sprint-05/sprint-review.md) | [✅](sprint-05/retrospective.md) | not captured |
| 6 | [✅](sprint-06/sprint-planning.md) | [✅](sprint-06/sprint-review.md) | [✅](sprint-06/retrospective.md) | not captured |
| 7 | [✅](sprint-07/sprint-planning.md) | [✅](sprint-07/sprint-review.md) | [✅](sprint-07/retrospective.md) | not captured |
| 8 | [✅](sprint-08/sprint-planning.md) | [prepared](sprint-08/sprint-review.md) (fill in 27 Nov) | [prepared](sprint-08/retrospective.md) (fill in 27 Nov) | screenshot at the review |
| 9 | | | | |

## Friday checklist (Scrum Master)

1. Before 22:00: run the weekly integration (`CONTRIBUTING.md` §5), then screenshot the sprint board and the
   Insights burndown/burn-up chart for the sprint.
2. Review: fill in `sprint-NN/sprint-review.md` (demoed items, accepted/rejected, PO feedback, velocity).
3. Retro: fill in `sprint-NN/retrospective.md` (went well / to improve / action items with owners).
4. Planning: create `sprint-(NN+1)/sprint-planning.md` (goal, capacity, committed items, points).
5. Update the velocity table in `scrum/timeline.md` and this index.
6. Close the sprint milestone. Move unfinished items to the next sprint, with their points re-estimated.
7. Post the sprint goal in `#announcements`.
