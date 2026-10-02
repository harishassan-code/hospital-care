# Discord Setup

About 15 minutes for a server admin. The goal: talk in Discord, track work in GitHub, and have
GitHub activity show up in Discord automatically.

## 1. Roles

Server Settings → Roles:

| Role | Colour | Who |
|---|---|---|
| `Scrum Master` | red | Haris |
| `Frontend` | purple | frontend devs |
| `Backend` | blue | backend devs |
| `QA/DevOps` | teal | whoever owns testing/CI that sprint |
| `Hospital Care` | default | all 8 members |

Tagging `@Backend` or `@Frontend` reaches the right people without pinging everyone.

## 2. Channels

Create a category per block. Names are suggestions, so keep whatever already exists if it fits.

**📌 INFO**
- `#announcements`: Scrum Master only (read-only for others). Sprint goals, deadlines, decisions.
- `#links`: pinned links to the repo, Project board, staging URLs, docs, Figma.

**🏃 SCRUM**
- `#daily-standup`: the bot posts the prompt at 10:00 and everyone replies **in a thread** by 23:59.
- `#sprint-ceremonies`: agenda, review notes, retro board link, planning results.
- `#backlog`: refinement questions and planning-poker votes.
- `#blockers`: anything blocking you more than half a day. The Scrum Master watches this channel.

**💻 DEV**
- `#frontend`
- `#backend`
- `#database`: schema/migration discussions (migration conflicts are the #1 integration pain).
- `#pull-requests`: post "PR ready: <link>" here, and reviewers react 👀 when they start and ✅ when they approve.
- `#help`: setup problems, "how do I…"

**🤖 FEEDS** (read-only for humans, mute if it gets noisy)
- `#github-feed`: issues, PRs, reviews and pushes from GitHub.
- `#ci-deploys`: CI failures and staging deploy notifications.

**🔊 VOICE**
- `Scrum Room`: Friday 22:00 ceremonies and optional daily check-ins.
- `Pairing 1`, `Pairing 2`: drop in for pair programming or debugging.

## 3. GitHub → Discord feed (no bot needed)

1. In Discord: `#github-feed` → ⚙️ Edit Channel → **Integrations → Webhooks → New Webhook** → name it
   `GitHub` → **Copy Webhook URL**.
2. In GitHub: repo → **Settings → Webhooks → Add webhook**
   - Payload URL: the webhook URL **with `/github` appended**, e.g. `https://discord.com/api/webhooks/123/abc/github`
   - Content type: `application/json`
   - Events: **Let me select individual events**, then tick *Issues, Pull requests, Pull request reviews,
     Pushes, Releases, Workflow runs*
3. Save. GitHub sends a ping and a message should appear in `#github-feed`.

Repeat with a second webhook in `#ci-deploys` and only the *Workflow runs* event if you want CI in
its own channel.

## 4. Stand-up and Friday reminders (already built into the repo)

`.github/workflows/discord-scrum-reminders.yml` posts:
- **10:00 PKT daily**: the stand-up prompt (Yesterday / Today / Blockers)
- **17:00 PKT Friday**: a reminder that ceremonies start at 22:00 with the agenda

To turn it on:
1. `#daily-standup` → Edit Channel → Integrations → Webhooks → New Webhook → name it `Scrum Bot` → copy URL.
2. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `DISCORD_SCRUM_WEBHOOK`
   - Value: the webhook URL (**without** `/github`)
3. Test it: repo → **Actions → Discord Scrum reminders → Run workflow**.

GitHub's scheduled workflows can run a few minutes late. That's normal.

## 5. Pin these in `#links`

- Repo: `https://github.com/harishassan-code/hospital-care`
- Board: GitHub Project *Hospital Care Scrum Board*
- Working agreement: `docs/scrum/working-agreement.md`
- Timeline: `docs/scrum/timeline.md`
- Staging frontend/API URLs (once deployed)

## 6. Stand-up format

Reply in the thread under the bot's message:

```
Yesterday: finished login form (#8), reviewed PR #14
Today: wire login form to API, start route guards (#10)
Blockers: none / waiting on @someone for the session endpoint
```
