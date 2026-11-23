# Staging Deployment

`main` deploys automatically to staging. The staging site is what we demo in sprint reviews.

| Part | Host | Config |
|---|---|---|
| API + Postgres | [Render](https://render.com) (free tier) | `render.yaml` |
| Frontend | [Vercel](https://vercel.com) (free Hobby tier) | `frontend/vercel.json` |

## One-time setup (Scrum Master)

### Backend on Render
1. Sign in to Render with GitHub and grant it access to the `hospital-care` repo.
2. **New → Blueprint** → pick the repo. Render reads `render.yaml` and creates the Postgres
   database and the `hospital-care-api` web service.
3. When it asks for `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`, enter the Vercel URL from the
   next step (for example `https://hospital-care.vercel.app`). You can fill these in after the frontend exists.
4. Check `https://<service>.onrender.com/api/health/` returns `{"status": "ok"}`.

Free-tier limits: the API sleeps after 15 minutes idle, so the first request takes about 30–60 s. **Open the
staging site about 2 minutes before every demo.** The free Postgres database expires after 30 days, so
recreate it (or move to a paid plan) before the final demo. Put this in the Sprint 8 planning.

### Frontend on Vercel
1. Sign in to Vercel with GitHub → **Add New → Project** → import `hospital-care`.
2. **Root Directory:** `frontend` (Vite is detected automatically).
3. Environment variable: `VITE_API_URL = /api`
4. Deploy. Every PR also gets a **preview URL**, which is useful for reviewing UI changes.

### How the two connect (one domain for the browser)
The browser only ever talks to the Vercel site. `frontend/vercel.json` forwards every `/api/...` request to
the Render API (with a `routes` rule, which Vercel checks before serving the app, so the app's catch-all
never answers `/api` instead), so the session and CSRF cookies belong to the Vercel domain. That matters: the frontend
reads the `csrftoken` cookie to send it back, and a page can't read a cookie set by another domain, so
calling `onrender.com` directly would let you log in but refuse every change after that with **403 CSRF**.
It also means no third-party cookies, so login works in Safari and on iPhones too.

If Render gives the API a different address than `https://hospital-care-api.onrender.com`, change the
`dest` of the `/api` route in `frontend/vercel.json` to match.

On Render, set `CSRF_TRUSTED_ORIGINS` (and `CORS_ALLOWED_ORIGINS`) to the Vercel URL, e.g.
`https://hospital-care.vercel.app`.

### Emergency escalation (story #35)
Critical emergency cases that stay unfulfilled are escalated automatically. The time is set by
`EMERGENCY_ESCALATION_MINUTES` (default `30`; a whole number of 1 or more, and the server refuses to start on any other
value). Set it on Render's **Environment** tab to change it. Nothing else is needed.

The free Render plan has no scheduled jobs, so the API runs the check itself whenever someone opens the case list or a
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
(quantity, distance). A weight for a factor the strategy does not use is refused. On Render, set `MATCHING_SCORING` on
the **Environment** tab.

### Resource holds (#43)
A reserved resource is held for a case for `RESERVATION_HOLD_MINUTES` (default `30`, a whole number of 1 or more; the
server refuses to start on any other value). When the hold runs out, the resource goes back to stock. Changing the value
does not move holds already made. Set it on Render's **Environment** tab.

The free Render plan has no scheduled jobs, so the API releases expired holds itself whenever someone opens a case, its
candidates or a reservation endpoint. A scheduler can run the same release with
`python manage.py release_expired_reservations`, which prints how many holds it released.

### HTTPS and deploy checks (B13)
With `DJANGO_DEBUG=false` (staging), the app:

- **refuses to start without `DJANGO_SECRET_KEY`**. Render generates the key (`generateValue` in `render.yaml`).
  Set a long random value (50 characters or more) by hand if you run the app anywhere else.
- **redirects plain HTTP to HTTPS** and sends `Strict-Transport-Security`. `/api/health/` is exempt, so Render's health
  check still passes. `DJANGO_HSTS_SECONDS` sets the HSTS length (default `3600`). Raise it to `31536000` after a week of
  HTTPS-only staging, since browsers cache it. Preload is off.
- sends the same HSTS header from the Vercel domain (`frontend/vercel.json`, `max-age=3600; includeSubDomains`). Change
  both when you change the length.
- does **not** route the Django admin at `/admin/` (it answers 404). The demo `admin@` login is a superuser, and its
  password is public in this document, so the admin is left off on staging. Set `DJANGO_ADMIN_ENABLED=true` on Render
  to route it, and back to `false` afterwards. Under `DJANGO_DEBUG=true` (local development) it is on.

Check the settings with the same command CI runs (a dummy key, so nothing secret is needed):

```bash
cd backend
DJANGO_DEBUG=false DJANGO_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(50))") \
  python manage.py check --deploy --fail-level WARNING
```

It should print `System check identified no issues`. CI runs the same command on every push, and
`apps/core/tests/test_deploy_settings.py` checks the settings too.

**On staging the build runs it too** (`render.yaml`, first step after installing packages), with staging's real
settings: a deploy that would be unsafe fails with the reason in the build log instead of going live. For the record
(B13, #58), copy the line `System check identified no issues (1 silenced).` from the first successful deploy's build
log into the operations notes.

### Sign-in and sign-up limits (B13)
Sign-in and sign-up each allow a number of requests per client address per period. The defaults are 30 per minute for
sign-in (`DJANGO_LOGIN_THROTTLE`) and 30 per hour for sign-up (`DJANGO_SIGNUP_THROTTLE`). Write a rate as `<count>/<period>`
with the period `second`, `minute`, `hour` or `day`, or leave it empty to turn that limit off. A bad rate stops the server.
The limits are generous because a hospital's computers often share one address. The per-account lockout after five
failed sign-ins is separate, and unchanged.

The address comes from `X-Forwarded-For` only through the proxies the deployment runs. `DJANGO_TRUSTED_PROXY_COUNT` is
the number of them: Render's proxy is `1` in `render.yaml`. Local development uses `0`, which means `REMOTE_ADDR`. The
value matters: too high lets a client choose its own address, and too low puts every user behind a proxy in one bucket.
Staging traffic also passes through Vercel's `/api` proxy, which may add a hop. That is not verified. Check it before
relying on the limit: from two different networks, a burst of sign-in attempts from one should not block the other.

### Demo data
The Render build runs `seed_demo` (it only adds data to empty tables), so staging has the demo hospitals,
beds, blood units and one login per role (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`,
`patient@demo.citycare.pk`, password `CityCare-demo-1`). These accounts are public test logins: never put
real patient data on staging.

### Before a demo
Run `python3 scripts/smoke_staging.py <vercel-url>` about 2 minutes before. It wakes the API and checks the health
endpoint through the Vercel proxy and the home page. The demo itself follows [demo-script.md](demo-script.md).
