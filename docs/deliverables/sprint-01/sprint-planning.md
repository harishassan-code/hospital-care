# Sprint 1 Planning

**Dates:** Sat 3 Oct – Fri 9 Oct 2026 · **Planning held:** Sat 3 Oct 2026 (project kickoff)
**Attendees:** _fill in_ · **Absent:** _fill in_

## Sprint goal
> **Foundation:** every member runs the project locally, the domain model (ERD) and wireframes are agreed,
> and a user can log in and out of Hospital Care end to end.

## Capacity

First sprint, so there's no velocity history yet. The commitment is a deliberately conservative **27 points** while the team learns
the stack and the workflow. Sprint 1 velocity becomes the baseline for Sprint 2 planning.

| Member | Available days (of 7) | Notes |
|---|---|---|
| Haris Hassan (SM, Frontend) | | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |
| | | |

## Committed backlog items

Owners are assigned by the Scrum Master on the board.

| Issue | Title | Type | Points | Owner |
|---|---|---|---|---|
| | Repository, CI pipeline and Docker dev environment | task | 3 | Haris (done at kickoff) |
| | Team onboarding: everyone runs the project locally | task | 1 | everyone |
| | Domain model and ERD for the MVP | task | 5 | |
| | UI wireframes for core user journeys | task | 5 | |
| | Frontend app shell: layout, routing, design tokens, API client | task | 3 | |
| | Document blood compatibility rules from an authoritative source | task | 2 | |
| | User accounts | story | 3 | |
| | Login, logout and session security | story | 5 | |

**Total:** 27 pts

## Risks and dependencies
- **Docker on Windows:** some members may not be able to run Docker Desktop. Option B (venv + SQLite) in the README is the fallback.
- **ERD blocks Sprint 2:** the shared Resource model and hospital models depend on it, so it must be reviewed by Thursday.
- **Auth across domains:** session cookies between Vercel and Render need cross-site settings, decided in the login story (see `docs/setup/deployment.md`).
- **Scope:** the WBS MVP is about 248 points over 9 sprints. If Sprint 1–2 velocity is below ~27, apply the scope-cut order in `docs/scrum/timeline.md` at the Sprint 4 mid-point check.
