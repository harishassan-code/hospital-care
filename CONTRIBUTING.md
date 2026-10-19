# Contributing

How code goes from an issue to `main`. Read this once and follow it every time.

**In short:** work on your own branch, push daily, get reviewed on your weekly pull request, and the Scrum Master
merges everyone's work into `main` every Friday.

## 1. Pick up work

1. Only take issues that are in the **current sprint** and in the **Ready** column of the board.
2. Assign yourself on the issue and move the card to **In Progress**.
3. Hold at most **2 items In Progress** at a time. Finish before starting something new.
4. If something blocks you for more than half a day, add the `blocked` label and post in `#blockers` on Discord.

## 2. Your branch

Everyone works on **their own branch**, named `<name>/<area>`, e.g. `haris/frontend`, `ali/backend-auth`.
Nobody commits to `main` directly: `main` only changes at the weekly integration (section 5).

Create it once, from an up-to-date `main`:

```bash
git checkout main
git pull
git checkout -b haris/frontend
git push -u origin haris/frontend
```

Then commit and **push at least once a day**. CI runs on every push to every branch, so you find out about
broken tests the same day, not on merge day.

If your work splits into separate areas (say, beds and pharmacy), finish one before starting the next, so a
problem in one doesn't hold back the other at integration.

## 3. Commit

[Conventional Commits](https://www.conventionalcommits.org/) style, present tense, with the issue number:

```
feat(blood): register blood units with expiry validation (#23)
fix(auth): stop leaking whether an email exists on failed login (#31)
docs(sprint-2): add retrospective notes
```

Write `Closes #23` in the commit body when a commit finishes an issue: the issue closes automatically when the
commit reaches `main` at integration. Never commit `.env` files, real patient/donor data, or credentials.

## 4. Your weekly pull request (where review happens)

1. Open **one pull request from your branch into `main`** at the start of the sprint and keep it open all week.
   Fill in the template.
2. **Don't merge it.** It exists so teammates can review your work and CI can report on it.
3. When an item is ready, move its card to **In Review** and post the PR link in `#pull-requests`.
4. **At least 1 approval** from a teammate before Friday. Backend changes reviewed by someone on backend, UI
   changes by someone on frontend, when possible.
5. After the weekly integration your PR shows as merged automatically. Open a fresh one for the next sprint.

### Reviewing

- Review within **24 hours** of being asked. Reviews are part of everyone's sprint work.
- Check the acceptance criteria, not just the code style.
- Use GitHub "suggestion" blocks for small fixes. Approve with nits rather than blocking on taste.

## 5. Weekly integration (Fridays, before the 22:00 ceremonies)

The Scrum Master combines everyone's work into `main` once a week:

1. Create `integration/<YYYY-MM-DD>` from `main`.
2. Merge each developer branch into it, one at a time, keeping everyone's commits (no squashing, so each
   person's contribution stays visible). Conflicts are resolved with the branch owner.
3. Run every check: backend and frontend tests, lint, build, and a click-through of every page.
4. Open a pull request from the integration branch into `main`. It needs one approval, then it's merged.
5. Merging to `main` deploys staging, which is what the sprint review demos.

**Right after integration, everyone updates their branch from `main`:**

```bash
git checkout haris/frontend
git fetch origin
git merge origin/main
git push
```

Skipping this step is the main cause of painful conflicts the following week.

### Shared files

Some files are touched by many people. Change them in small, separate commits and say so in `#frontend` or
`#backend` the same day:

| File | Why it conflicts |
|---|---|
| `frontend/package.json`, `package-lock.json` | Everyone adds packages |
| `frontend/src/App.tsx` | Every new page adds a route |
| `frontend/src/styles/tokens.css` | Shared colours, fonts, spacing |
| `backend/config/settings.py`, `backend/*/migrations/` | Shared configuration and database schema |

## Database migrations

- Commit migrations with the model change, in the same commit.
- Never edit a migration that is already on `main`. Write a new one instead.
- If two branches create conflicting migrations, they're reconciled at integration with
  `python manage.py makemigrations --merge`.

## Code conventions

- **Backend:** each module lives in its own app under `backend/apps/`. Business rules go in
  `services.py`/domain classes, not in views or serializers. Every endpoint has a permission class
  and a test.
- **Frontend:** pages in `src/pages/`, reusable UI in `src/components/`, API calls only through `src/api/`.
- Format before committing: `ruff format .` (backend) and keep `npm run lint` clean (frontend).
