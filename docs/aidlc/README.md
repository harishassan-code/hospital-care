# AIDLC: AI-Driven Development Life Cycle

This project uses AIDLC alongside Scrum to structure how AI-assisted feature work moves from idea to
production. It does not replace the Scrum ceremonies in [docs/deliverables](../deliverables/README.md) —
it describes the three phases a single feature or story passes through *within* a sprint, each with a
human approval gate before the next phase starts.

| Phase | What happens | Approval gate | Template |
|---|---|---|---|
| [Inception](#1-inception) | Requirements captured as a spec: problem, user stories, acceptance criteria, open questions | Product Owner signs off on the spec before any code is written | [inception-spec-template.md](templates/inception-spec-template.md) |
| [Construction](#2-construction) | The approved spec becomes a technical plan broken into small units, each built on a branch and opened as a PR | A reviewer approves the PR (enforced by branch protection, see [CONTRIBUTING.md](../../CONTRIBUTING.md)) | [construction-plan-template.md](templates/construction-plan-template.md) |
| [Operations](#3-operations) | CI runs, the PR merges, the change ships through the staging pipeline, and the outcome is observed | PO/team reviews the deployed outcome; follow-ups feed the next Inception | [operations-notes-template.md](templates/operations-notes-template.md) |

## 1. Inception

Before any implementation starts, write an inception spec using the
[template](templates/inception-spec-template.md) and save it under `docs/aidlc/inception/`
(e.g. `docs/aidlc/inception/2026-11-11-feature-name.md`).

The spec covers:

- The problem being solved and who it's for.
- User stories and acceptance criteria.
- Open questions / explicit non-goals.
- A sign-off line naming who approved it and when.

**Worked examples:** the two existing design docs in
[`docs/superpowers/specs/`](../superpowers/specs/) were written in this spirit before their
corresponding features were built, and are good references for the level of detail expected.

No code is written until the spec is approved.

## 2. Construction

Once a spec is approved, write a construction plan using the
[template](templates/construction-plan-template.md) and save it under `docs/aidlc/construction/`,
mirroring the spec's filename. The plan breaks the spec into small, independently reviewable units
(each one roughly a single PR), lists the files each unit touches, and names the tests that will
cover it.

Each unit is then implemented on its own branch and opened as a pull request. This project's branch
protection already requires a reviewer's approval before merge (see
[CONTRIBUTING.md](../../CONTRIBUTING.md)) — that review **is** the AIDLC construction gate, so no
separate process is added here.

## 3. Operations

After a PR merges, CI and the staging pipeline (Render + Vercel, see
[docs/setup/deployment.md](../setup/deployment.md)) take over. Once the feature is live on staging,
record the outcome using the [template](templates/operations-notes-template.md) under
`docs/aidlc/operations/`: what shipped, any monitoring notes, and follow-up items.

Follow-ups and issues observed here feed directly into the next Inception spec, and are also visible
in the sprint review/retrospective docs under [docs/deliverables](../deliverables/README.md).

## 4. Bolts

The remaining backlog is split into **bolts**: the AIDLC unit of delivery. A bolt is one short, time-boxed cycle
(1–3 days) through Inception → Construction → Operations, owned by one person working with an AI assistant. It
covers one backlog story (sometimes two or three small, related ones) and is sized to finish inside a sprint.

| Scrum | AIDLC |
|---|---|
| Epic (E6 Transfers & Logistics) | Intent: the outcome the epic is after |
| Story / issue (#47) | Unit of work, described in the issue's acceptance criteria |
| Sprint (1 week) | Contains several bolts; each bolt finishes inside it |
| Task on the board | **Bolt** (`docs/aidlc/bolts/B01-transfer-request.md`): the issue(s), the existing code to build on, scope, open questions, exit checklist |

**The board:** [bolts/README.md](bolts/README.md), generated from each bolt's front matter by
`scripts/aidlc_board.py`. CI runs `python3 scripts/aidlc_board.py --check`, so the board always matches the files.

**Taking a bolt (team members):**

1. Pick a 🟢 Ready bolt on the [board](bolts/README.md) (all its dependencies are Done). Agree on it at planning or
   in `#daily-standup`.
2. In the bolt file set `owner:` to your GitHub handle and `status: In Progress`, run
   `python3 scripts/aidlc_board.py`, and assign yourself the linked issue(s). Max 2 in progress per person.
3. Run the three phases above. With Claude Code: `/bolt-start B01`, then `/aidlc-construction B01`, then
   `/aidlc-operations B01` (see [CLAUDE.md](../../CLAUDE.md)). With another assistant, give it
   [AGENTS.md](../../AGENTS.md) and the bolt file.
4. The Scrum Master (or PO) signs the Inception spec's Approval line before any code is written.
5. When it's merged and checked on staging: tick the bolt's exit checklist, set `status: Done`, regenerate the
   board, close the issue(s). Move any bolt it unblocked from Backlog to Ready.

**Writing a new bolt:** copy [templates/bolt-template.md](templates/bolt-template.md) to
`bolts/BNN-<slug>.md` with the next free number, fill it in (especially **Build on**), and regenerate the board.

## 5. The AI assistant environment

The repository carries everything an assistant needs to follow this process:

| File | Purpose |
|---|---|
| [AGENTS.md](../../AGENTS.md) | The rules for any AI assistant: the AIDLC gates, codebase conventions, the checks to run |
| [CLAUDE.md](../../CLAUDE.md) | Loads AGENTS.md into Claude Code and lists the slash commands |
| [.claude/commands/](../../.claude/commands/) | `/bolt-start`, `/aidlc-construction`, `/aidlc-operations`, `/bolt-board` |
| [templates/](templates/) | Inception spec, construction plan, operations notes, bolt |
| [scripts/aidlc_board.py](../../scripts/aidlc_board.py) | Builds and checks the bolt board |

## Why this on top of Scrum

Scrum answers *what we build this sprint and in what order*. AIDLC answers *how a single piece of
that work moves from an AI-drafted idea to something running in production, with a human approving
it at each handoff*. The two are complementary: a sprint's committed backlog items each go through
their own Inception -> Construction -> Operations cycle.
