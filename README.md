# Hospital Care

City-wide hospital emergency resource coordination platform (project codename **CityCare**).
Hospitals share blood, beds, equipment, operating rooms and ambulances through one network, so an
emergency request can find, reserve and transfer what it needs from the nearest capable hospital.

Built for the **Agile Software Project Management** course using Scrum, with 1-week sprints from
3 Oct 2026 to the final demo in early December 2026.

| | |
|---|---|
| **Board** | [Hospital Care Scrum Board](https://github.com/users/harishassan-code/projects/1) |
| **Sprints** | [Milestones](../../milestones) · [Timeline](docs/scrum/timeline.md) |
| **How we work** | [Working agreement](docs/scrum/working-agreement.md) · [Contributing](CONTRIBUTING.md) |
| **Course deliverables** | [docs/deliverables](docs/deliverables/README.md) |
| **Backlog snapshot** | [docs/product/backlog.md](docs/product/backlog.md) |
| **Architecture** | [docs/architecture](docs/architecture/README.md) |
| **Team** | [docs/scrum/team.md](docs/scrum/team.md) |

## Tech stack

- **Frontend:** React 19 + TypeScript + Vite, React Router, Vitest + Testing Library, oxlint
- **Backend:** Django 6 + Django REST Framework, pytest, ruff
- **Database:** PostgreSQL 17
- **Dev environment:** Docker Compose
- **CI:** GitHub Actions (lint + tests + build on every PR)
- **Staging:** Render (API + Postgres), Vercel (frontend); see [deployment guide](docs/setup/deployment.md)

## Repository layout

```
backend/            Django project
  config/           settings, root URLs
  apps/             one Django app per module (accounts, hospitals, resources, blood,
                    emergencies, matching, transfers, notifications, audit, core)
frontend/           React app (src/pages, src/api, ...)
docs/               process, product, architecture and course deliverables
scripts/            backlog + GitHub sync tooling
.github/            CI, issue/PR templates, Discord reminder workflow
```

## Running locally

### Option A: Docker (recommended, everything in one command)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
docker compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000/api/health/
- Django admin: http://localhost:8000/admin/ (create a user with
  `docker compose exec backend python manage.py createsuperuser`)
- Demo data and a login per role: `docker compose exec backend python manage.py seed_demo`
  (see the [API reference](docs/architecture/api.md))

### Option B: Without Docker

Backend (Python 3.13+). Without `DATABASE_URL` it falls back to SQLite, which is fine for quick work:

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows (Git Bash: source .venv/Scripts/activate) · macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_demo      # demo wards, beds, blood, medicines, doctors and one login per role
python manage.py runserver
```

Frontend (Node 24+):

```bash
cd frontend
npm install
npm run dev
```

### Signing in

Open http://localhost:5173/login and use one of the demo accounts listed in
[docs/architecture/api.md](docs/architecture/api.md#demo-data) (one per role). Staff land in the staff workspace at
`/staff` and see only the modules their role allows; patients land on the home page. The frontend talks to the
API at `VITE_API_URL` (default `http://localhost:8000/api`), so both servers must be running.

### Checks to run before pushing (CI runs the same ones)

```bash
cd backend && ruff check . && ruff format --check . && pytest
cd frontend && npm run lint && npm test && npm run build
```
