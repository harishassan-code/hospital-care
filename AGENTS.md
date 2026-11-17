# Instructions for AI coding assistants

These rules apply to any AI assistant working in this repository (Claude Code, Copilot, Cursor, ChatGPT…).
Claude Code loads them through [CLAUDE.md](CLAUDE.md). Humans: the same rules are in
[CONTRIBUTING.md](CONTRIBUTING.md) and [docs/aidlc/README.md](docs/aidlc/README.md).

## What this project is

Hospital Care (codename CityCare): a city-wide platform where hospitals share blood, beds, equipment, operating
rooms and ambulances, so an emergency case can find, reserve and transfer what it needs. Django 6 + DRF backend
(`backend/apps/<module>/`), React 19 + TypeScript frontend (`frontend/src/`). Built by a student Scrum team for
the ASPM course; the Product Owner is the course instructor.

## How work is organised: AIDLC bolts

All feature work runs as **bolts**: short AIDLC cycles listed on the
[bolt board](docs/aidlc/bolts/README.md), one file per bolt in `docs/aidlc/bolts/`. Each bolt says what to build,
which issues it closes, the existing code to build on, and the open questions.

Every bolt goes through three phases, each with a human gate. **Never skip a gate.**

1. **Inception.** Write the spec in `docs/aidlc/inception/<YYYY-MM-DD>-<slug>.md` from
   `docs/aidlc/templates/inception-spec-template.md`, using the bolt file and its issues. Answer the bolt's open
   questions as *proposals* for the human to approve. **Write no code until the spec's Approval line is signed.**
2. **Construction.** Write the plan in `docs/aidlc/construction/<same file name>` from
   `construction-plan-template.md`: small units, each about one commit or PR, with files and tests. Then build
   unit by unit. A reviewer's PR approval is the gate.
3. **Operations.** Once it's live on staging, write `docs/aidlc/operations/<same file name>` from
   `operations-notes-template.md` (what shipped, what to watch, follow-ups).

When the human starts a bolt, set `owner:` and `status: In Progress` in its file. When it's merged, set
`status: Done`. Either way, run `python3 scripts/aidlc_board.py` afterwards so the board matches.

## Rules that keep the codebase consistent

- **Business rules live in `services.py`** (or a domain module), not in views or serializers. Every endpoint has a
  permission class and a test.
- **Access control is one table in two places:** `backend/apps/accounts/permissions.py` (enforced) and
  `frontend/src/features/staff/roles.ts` (hides UI). Change both together and update
  `docs/architecture/api-contracts.md`.
- **Every state change is audit-logged** with `apps.audit.services.record(actor, "<object>.<verb>", target, ...)`.
- **Status changes go through `apps.resources.state_machine.StateMachine`.** Anything that moves stock between
  states, or between hospitals, runs inside `transaction.atomic()` with `select_for_update()` (see
  `apps/matching/reservations.py` and `allocations.py`).
- **Reuse before you write.** Each bolt's "Build on" section lists the existing code to use. In particular:
  `reserve`/`release` (holds), `allocate` (allocation + case recompute), `candidates_for_case` (ranked sources),
  `distance.py`, `seed_demo` (demo data).
- **Frontend:** pages in `src/pages/`, reusable UI in `src/components/`, API calls only through `src/api/`. Mock
  new endpoints in `src/test/mockApi.ts` so tests run against the real API shape. When a placeholder module gets a
  real page, remove it from `src/features/staff/planned.ts`.
- **Migrations** are committed with the model change. Never edit one that is already on `main`.
- **Data:** demo data is synthetic. Never add real patient data, names or secrets.
- **QA tests** live in `frontend/src/qa/features.qa.test.tsx`. Check for specific links/items
  (`arrayContaining`, `not.toContain`), never an exact menu list, so new modules don't break them.

## Checks before every commit (CI runs the same)

```bash
cd backend && ruff check . && ruff format --check . && python manage.py makemigrations --check --dry-run && python -m pytest -q
```

```bash
cd frontend && npm run lint && npm test && npm run build
```

```bash
python3 scripts/check_deploy_config.py && python3 scripts/aidlc_board.py --check
```

Tests that need PostgreSQL skip on SQLite and run in CI.

## Git

- Work on your own branch `<name>/<area>` (e.g. `ali/b01-transfers`) and push daily; one weekly PR into `main`
  (see [CONTRIBUTING.md](CONTRIBUTING.md)).
- Mention the bolt and issue in commit messages, e.g. `feat(transfers): approve or reject a request (B01, #47)`.
- Credit the human who owns the work as the author. The assistant is a co-author, not the owner.
