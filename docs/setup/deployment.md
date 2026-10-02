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
3. Environment variable: `VITE_API_URL = https://<service>.onrender.com/api`
4. Deploy. Every PR also gets a **preview URL**, which is useful for reviewing UI changes.

### Login across domains
The frontend and API are on different domains, so before login ships (Sprint 1), the auth story must
set `SESSION_COOKIE_SAMESITE="None"`, `SESSION_COOKIE_SECURE=True`, and the same for the CSRF
cookie in non-debug settings. The alternative is token auth. Decide this in the login story.
