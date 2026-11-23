# Staging Deployment

`main` deploys automatically to staging. The staging site is what we demo in sprint reviews.

Staging is **one [Vercel](https://vercel.com) project** (free Hobby plan) that serves both halves on one domain, set
up by `vercel.json` at the repository root:

| Part | Where it runs on Vercel | Config |
|---|---|---|
| Frontend (React, `frontend/`) | the `web` service: static files, with `index.html` for every page address | `vercel.json` → `services.web` |
| API (Django, `backend/`) | the `api` service: a Python function that answers `/api/...` | `vercel.json` → `services.api`, `backend/pyproject.toml`, `backend/vercel_build.sh` |
| Database | PostgreSQL from **Neon** (free), connected from the project's **Storage** tab | `DATABASE_URL`, set by Vercel |

(Until 23 Nov the plan was the API on Render and the site on Vercel. render.com wasn't reachable from the team's
network, so both moved to Vercel; the app itself doesn't depend on the host.)

## One-time setup (Scrum Master)

1. **Import the project.** Sign in to Vercel with GitHub → **Add New → Project** → import `hospital-care`.
   - **Framework Preset:** choose **Services** (one project, several parts: here the site and the API).
   - **Root Directory:** leave it as the repository root (`./`), not `frontend`.
   - **Environment Variables:** add `DJANGO_SECRET_KEY` with a long random value (50 characters or more), for all
     environments. Make one with `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`. Nothing else is
     needed: on Vercel the app turns DEBUG off and allows `*.vercel.app` by itself (`backend/config/settings.py`).
   - **Deploy.** The first deploy stops with *DATABASE_URL is not set*. That's expected: there is no database yet.
2. **Add the database.** In the project, open **Storage → Create Database → Neon (Postgres)**, keep the free plan,
   and connect it to the project for all environments. Vercel adds `DATABASE_URL` (pooled) and
   `DATABASE_URL_UNPOOLED` (direct) to the project's variables. For the region, pick the one closest to the API:
   Vercel runs it in Washington, D.C. (US East) unless you change **Settings → Functions → Function Region**.
3. **Redeploy.** **Deployments** → the failed deploy → **Redeploy**. The API's build step (`backend/vercel_build.sh`)
   runs the deploy check, then the migrations, and fills the empty database with the demo data.
4. **Check it.** `python3 scripts/smoke_staging.py https://<project>.vercel.app` passes, `/api/health/` shows
   `{"status": "ok"}`, and you can sign in and save a change. Put the address in the [README](../../README.md#staging).

From then on every push to `main` deploys to production, and every pull request gets a **preview URL**, useful for
reviewing UI changes. A preview uses the same database but never migrates it, so a pull request that adds a migration
may show errors on its preview until it is merged.

Free-plan limits: the API starts on demand, and the database sleeps after a few minutes idle, so the first request
after a quiet spell takes a few seconds. **Open the staging site about 2 minutes before every demo.** Neon's free
database doesn't expire.

### The live city simulation (B21)
On Vercel the network runs a simulation of a city (`SIMULATION_ENABLED` is on there by default; set it to `false` to
stop it). There is no background worker on the free plan: each open page asks the API to run the city up to its clock
every 20 seconds, so the city sleeps while nobody has the site open and catches up when someone returns. The CityCare
admin (`network@demo.citycare.pk`) runs the clock from **Simulation** in the staff menu. Before the scripted demo,
pause it or leave it running: it never touches the demo's stock. After fast-forwarding more than about six days, run the
reset below first. Everything else: [docs/product/simulation.md](../product/simulation.md).

### How the two halves share one domain
The browser only ever talks to one address. `vercel.json` sends `/api/...` to the Django service and everything else
to the site, so the session and CSRF cookies belong to the site's own domain. That matters: the frontend reads the
`csrftoken` cookie to send it back, and a page can't read a cookie set by another domain. It also means no third-party
cookies, so sign-in works in Safari and on iPhones too, and no CORS or CSRF origins to configure. The frontend is built
with `VITE_API_URL=/api` (the `web` service's build command), so it calls the API on the same domain.
`scripts/check_deploy_config.py` checks all of this in CI.

### Emergency escalation (story #35)
Critical emergency cases that stay unfulfilled are escalated automatically. The time is set by
`EMERGENCY_ESCALATION_MINUTES` (default `30`; a whole number of 1 or more, and the server refuses to start on any other
value). Set it under the Vercel project's **Settings → Environment Variables**, then redeploy. Nothing else is needed.

Staging runs no scheduled jobs, so the API runs the check itself whenever someone opens the case list or a
case. A scheduler can run the same check with `python manage.py escalate_overdue_cases`, which prints how many cases it
escalated. Running it twice escalates nothing the second time.

### Candidate scoring (story #40)
The order of candidate hospitals is set by strategy and weights. Set `MATCHING_SCORING` (JSON, keyed by resource type)
and optionally `MATCHING_MAX_DISTANCE_KM` (default `50`, a whole number of 1 or more). Anything not mentioned keeps its
default: blood uses `earliestExpiry`, and beds, equipment and operating rooms use `nearest`. Weights not mentioned keep
the strategy's defaults. Weights are relative, so they need not add up to 1. The server refuses to start on a bad value,
with a message that names the problem. This changes no API or screen; the scores themselves are shown by a later story.

```json
{"blood": {"strategy": "earliestExpiry", "weights": {"expiry": 0.6, "distance": 0.4}}, "bed": {"strategy": "mostStock"}}
```

Strategies: `earliestExpiry` (expiry, compatibility, distance, quantity), `nearest` (distance, quantity) and `mostStock`
(quantity, distance). A weight for a factor the strategy does not use is refused. On Vercel, set `MATCHING_SCORING` under
**Settings → Environment Variables**, then redeploy.

### Resource holds (#43)
A reserved resource is held for a case for `RESERVATION_HOLD_MINUTES` (default `30`, a whole number of 1 or more; the
server refuses to start on any other value). When the hold runs out, the resource goes back to stock. Changing the value
does not move holds already made. Set it under the Vercel project's **Settings → Environment Variables**.

Staging runs no scheduled jobs, so the API releases expired holds itself whenever someone opens a case, its
candidates or a reservation endpoint. A scheduler can run the same release with
`python manage.py release_expired_reservations`, which prints how many holds it released.

### HTTPS and deploy checks (B13)
With `DJANGO_DEBUG=false` (staging), the app:

- **refuses to start without `DJANGO_SECRET_KEY`**. On Vercel it is the one variable you set by hand (step 1 above):
  a long random value, 50 characters or more.
- **redirects plain HTTP to HTTPS** and sends `Strict-Transport-Security`. `/api/health/` is exempt, so a host's health
  check still passes. `DJANGO_HSTS_SECONDS` sets the HSTS length (default `3600`). Raise it to `31536000` after a week of
  HTTPS-only staging, since browsers cache it. Preload is off.
- sends the same HSTS header with the site's pages (`vercel.json`, `services.web.headers`, `max-age=3600;
  includeSubDomains`). Change both when you change the length.
- does **not** route the Django admin at `/admin/` (it answers 404). The demo `admin@` login is a superuser, and its
  password is public in this document, so the admin is left off on staging. Set `DJANGO_ADMIN_ENABLED=true` on Vercel
  to route it, and back to `false` afterwards. Under `DJANGO_DEBUG=true` (local development) it is on.

Check the settings with the same command CI runs (a dummy key, so nothing secret is needed):

```bash
cd backend
DJANGO_DEBUG=false DJANGO_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))") \
  python manage.py check --deploy --fail-level WARNING
```

It should print `System check identified no issues`. CI runs the same command on every push, and
`apps/core/tests/test_deploy_settings.py` checks the settings too.

**On staging the build runs it too** (`backend/vercel_build.sh`, first step after installing packages), with staging's
real settings: a deploy that would be unsafe fails with the reason in the build log instead of going live. For the record
(B13, #58), copy the line `System check identified no issues (1 silenced).` from the first successful deploy's build
log into the operations notes.

### Sign-in and sign-up limits (B13)
Sign-in and sign-up each allow a number of requests per client address per period. The defaults are 30 per minute for
sign-in (`DJANGO_LOGIN_THROTTLE`) and 30 per hour for sign-up (`DJANGO_SIGNUP_THROTTLE`). Write a rate as `<count>/<period>`
with the period `second`, `minute`, `hour` or `day`, or leave it empty to turn that limit off. A bad rate stops the server.
The limits are generous because a hospital's computers often share one address. The per-account lockout after five
failed sign-ins is separate, and unchanged.

The address comes from `X-Forwarded-For` only through the proxies the deployment runs. `DJANGO_TRUSTED_PROXY_COUNT` is
the number of them: on Vercel it is `1` (Vercel's edge, which writes the visitor's address itself). Local development
uses `0`, which means `REMOTE_ADDR`. The value matters: too high lets a client choose its own address, and too low puts
every user behind a proxy in one bucket. Because site and API are one Vercel project, there is no second proxy in
between. Check it once on staging before relying on the limit: from two different networks, a burst of sign-in attempts
from one should not block the other. On Vercel the counts are kept in the database (`DJANGO_CACHE=database`, the
default there), because several copies of the API run at once and each would otherwise count on its own.

### Demo data
Every production build runs `seed_demo` (it only adds data to empty tables), so staging has the demo hospitals,
beds, blood units and one login per role (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`,
`patient@demo.citycare.pk`, password `CityCare-demo-1`). These accounts are public test logins: never put
real patient data on staging.

### Before a demo
Run `python3 scripts/smoke_staging.py <site>` about 2 minutes before. It wakes the API and the database and checks the
health endpoint through the site's `/api` and the home page. The demo itself follows [demo-script.md](demo-script.md).
