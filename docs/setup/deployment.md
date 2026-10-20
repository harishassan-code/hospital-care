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
the Render API, so the session and CSRF cookies belong to the Vercel domain. That matters: the frontend
reads the `csrftoken` cookie to send it back, and a page can't read a cookie set by another domain, so
calling `onrender.com` directly would let you log in but refuse every change after that with **403 CSRF**.
It also means no third-party cookies, so login works in Safari and on iPhones too.

If Render gives the API a different address than `https://hospital-care-api.onrender.com`, change the
`destination` in `frontend/vercel.json` to match.

On Render, set `CSRF_TRUSTED_ORIGINS` (and `CORS_ALLOWED_ORIGINS`) to the Vercel URL, e.g.
`https://hospital-care.vercel.app`.

### Demo data
The Render build runs `seed_demo` (it only adds data to empty tables), so staging has the demo hospitals,
beds, blood units and one login per role (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`,
`patient@demo.citycare.pk`, password `CityCare-demo-1`). These accounts are public test logins: never put
real patient data on staging.
