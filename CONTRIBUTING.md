# Contributing

How code goes from an issue to `main`. Read this once and follow it every time.

## 1. Pick up work

1. Only take issues that are in the **current sprint** and in the **Ready** column of the board.
2. Assign yourself on the issue and move the card to **In Progress**.
3. Hold at most **2 items In Progress** at a time. Finish before starting something new.
4. If something blocks you for more than half a day, add the `blocked` label and post in `#blockers` on Discord.

## 2. Branch

Always branch from an up-to-date `main`:

```bash
git checkout main
git pull
git checkout -b feat/23-blood-unit-registration
```

Format: `<type>/<issue-number>-<short-description>`

| type | for |
|---|---|
| `feat` | new feature / user story |
| `fix` | bug fix |
| `chore` | setup, tooling, dependencies |
| `docs` | documentation and course deliverables |
| `test` | tests only |
| `refactor` | code change with no behaviour change |

Keep branches short-lived: open the PR within **2 days**. Split big stories into several PRs.

## 3. Commit

[Conventional Commits](https://www.conventionalcommits.org/) style, present tense:

```
feat(blood): register blood units with expiry validation
fix(auth): stop leaking whether an email exists on failed login
docs(sprint-2): add retrospective notes
```

Never commit `.env` files, real patient/donor data, or credentials.

## 4. Pull request

1. Push and open a PR into `main`. The template loads automatically, so fill it in.
2. Write `Closes #<issue>` so the issue closes on merge.
3. Move the card to **In Review** and post the PR link in `#pull-requests` on Discord.
4. CI must be green.
5. **At least 1 approval** from a teammate is required. Backend changes should be reviewed by someone
   else on backend, and UI changes by someone on frontend, when possible.

### Reviewing

- Review within **24 hours** of being asked. Reviews are part of everyone's sprint work.
- Check the acceptance criteria, not just the code style.
- Use GitHub "suggestion" blocks for small fixes. Approve with nits rather than blocking on taste.

## 5. Merge

- **Squash and merge**, with the PR title as the commit message.
- Delete the branch after merging.
- Merging to `main` auto-deploys staging, so never merge something that breaks the build.

## Database migrations

- Commit migrations with the model change, in the same PR.
- Never edit a migration that is already on `main`. Write a new one instead.
- If two PRs create conflicting migrations, whoever merges second rebases and runs
  `python manage.py makemigrations --merge`.

## Code conventions

- **Backend:** each module lives in its own app under `backend/apps/`. Business rules go in
  `services.py`/domain classes, not in views or serializers. Every endpoint has a permission class
  and a test.
- **Frontend:** pages in `src/pages/`, reusable UI in `src/components/`, API calls only through `src/api/`.
- Format before committing: `ruff format .` (backend) and keep `npm run lint` clean (frontend).
