# Working Agreement

How the Hospital Care team runs Scrum. Any change to this agreement is proposed in a retrospective.

## Roles

| Role | Who | Responsibilities |
|---|---|---|
| Product Owner | Course instructor | Owns the product vision, sets priorities, accepts or rejects increments at sprint review |
| Scrum Master | Haris Hassan | Facilitates events, removes impediments, keeps the board and deliverables up to date. Also a frontend developer |
| Development Team | All 8 members | Design, build, test, review, document. Ownership areas are assigned by the Scrum Master each sprint |

Because the PO is the instructor and not always available, the Scrum Master acts as **PO proxy**
between reviews: they order the backlog based on the instructor's feedback and the proposal. Any
scope question the proxy can't answer goes to the instructor at the next opportunity.

## Sprint cadence (1-week sprints)

A sprint runs **Saturday → Friday**. All ceremonies happen in one Friday call so the team only
needs one long meeting per week.

| When | Event | Length | Output |
|---|---|---|---|
| Daily | **Stand-up** in `#daily-standup` (async, reply by 23:59). A short live voice check-in is optional | 2 min to write | Yesterday / Today / Blockers |
| Mid-week (Tue/Wed) | **Backlog refinement**, async in `#backlog` plus 20 min voice if needed | 20 min | Next sprint's stories meet the Definition of Ready |
| **Friday 22:00 PKT** | **Sprint Review**: demo the increment from staging | 20 min | Review notes, PO feedback |
| | **Retrospective**: what went well / what didn't / actions | 20 min | 1–3 action items, each with an owner |
| | **Sprint Planning** for the sprint starting Saturday | 30 min | Sprint goal, committed items, points |

Ceremonies are held in the **🔊 Scrum Room** voice channel. If someone can't attend, they post their
demo/notes in `#sprint-ceremonies` before 22:00.

## Definition of Ready (before an item can enter a sprint)

- [ ] Clear user and value statement ("As a… I want… so that…")
- [ ] Acceptance criteria written and understood by the team
- [ ] Dependencies and assumptions identified
- [ ] Small enough for one sprint (≤ 8 points; 13-pointers must be split)
- [ ] UI/API/data impact understood well enough to estimate

## Definition of Done (before an item counts as done)

- [ ] Implementation complete and merged to `main` through a reviewed PR
- [ ] All acceptance criteria pass
- [ ] Unit/API tests written and CI green
- [ ] Reviewed and approved by at least one other team member
- [ ] Migrations/schema changes documented in the PR
- [ ] No known critical or high-severity bug remaining for the item
- [ ] Deployed to staging and shown in the sprint review
- [ ] Relevant docs updated

Only items meeting the DoD count towards velocity. Partly done work goes back to the backlog
and is re-estimated.

## Estimation

- Story points on a Fibonacci scale: **1, 2, 3, 5, 8, 13**.
- Estimated together with planning poker in Discord (everyone posts their number at the same time,
  then the highest and lowest explain their reasoning).
- Reference stories: *Donor registration* = 3, *Blood unit registration* = 5, *Atomic resource reservation* = 8.

## Board workflow

`Backlog → Ready → In Progress → In Review → Done`

- **Backlog:** not yet refined or not in this sprint.
- **Ready:** in the current sprint and meets the DoR.
- **In Progress:** has an assignee and a branch. Max 2 per person.
- **In Review:** PR open and review requested.
- **Done:** PR merged and the DoD is met.

## Communication norms

- Discord is for conversation; **decisions are recorded in GitHub** (an issue comment or a docs PR).
- Reply to direct mentions within **12 hours** on weekdays.
- Questions about a specific task go in the issue thread, so the context stays with the work.
- If you're going to miss a stand-up or ceremony, say so in advance in `#daily-standup`.
- Be kind in reviews. Critique the code, not the person.

## Escalation

1. Blocked for more than half a day → `blocked` label and a post in `#blockers`.
2. Still blocked after 24 h → the Scrum Master pairs someone with you or re-plans the item.
3. Sprint goal at risk → the Scrum Master raises it at the next stand-up, and the team agrees what to drop.
