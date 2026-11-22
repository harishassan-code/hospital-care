# Candidate search load test (B13)

**Bolt:** [B13](../aidlc/bolts/B13-security-performance.md) · **Issue:** [#58](https://github.com/harishassan-code/hospital-care/issues/58)
**Date:** 2026-11-18 · **Code:** commit `ce9ae8c` (the script; `seed_demo --hospitals` is in `b7d9e82`)
**Script:** [`scripts/load_test_search.py`](../../scripts/load_test_search.py) · **Spec:** [Q1 to Q4](../aidlc/inception/2026-11-18-security-performance.md)

## Result

Candidate search, `GET /api/emergencies/<reference>/candidates/`, against a 50-hospital network, one synchronous
gunicorn worker (as `render.yaml` runs it), SQLite on a laptop. Every timed request succeeded.

| Concurrency | p50 ms | **p95 ms** | p99 ms | max ms | Requests | Errors |
|---|---|---|---|---|---|---|
| 1 | 8.9 | **12.5** | 13.2 | 32.7 | 200 | 0 |
| 5 | 46.6 | **49.1** | 70.3 | 70.3 | 200 | 0 |

Repeat runs, same command, same server, a few minutes apart:

| Run | Concurrency | p50 ms | p95 ms | p99 ms | max ms | Load average before / after (8 cores) |
|---|---|---|---|---|---|---|
| A (first, outlier) | 1 | 20.9 | 88.8 | 142.8 | 158.3 | not recorded |
| A | 5 | 59.4 | 74.4 | 85.5 | 89.1 | not recorded |
| B | 1 | 8.9 | 12.5 | 13.2 | 32.7 | 2.80 / 2.73 |
| B | 5 | 46.6 | 49.1 | 70.3 | 70.3 | (same run) |
| C | 1 | 8.9 | 12.5 | 15.7 | 33.6 | 2.73 / 2.68 |
| C | 5 | 46.5 | 51.3 | 68.9 | 68.9 | (same run) |

Run A is kept in the table, not removed, and its cause is not established. Its load was not recorded, and another
test run on the same machine was observed afterwards, so the cause is not confirmed. Runs B and C ran at the same
load, and agree at concurrency 1 (12.5 ms p95 both times) and within 2.5 ms at concurrency 5.
**Recorded p95, the figure for the final report: 12.5 ms at concurrency 1, and 49 to 51 ms at concurrency 5.**

## Dataset

Row counts for the scratch database after `seed_demo --hospitals 50`, before any run (all synthetic). The case count is
taken after the runs, since the runs create the cases:

| Table | Rows | Note |
|---|---|---|
| Hospitals | 50 | 3 named demo hospitals, 47 synthetic |
| Wards | 153 | |
| Beds | 1668 | 238 free |
| Blood units | 1104 | 1049 available |
| Donors | 60 | |
| Donation appointments | 6 | |
| Equipment | 113 | |
| Operating rooms | 150 | |
| Operating-room bookings | 300 | |
| Medicines | 23 | |
| Users | 6 | one per demo role |
| Emergency cases | 0 before the runs, 4 after | one dry run and three recorded runs |

Each run's case was at the origin hospital (CityCare General) and asked for one need of each type at the largest
quantity the API allows per line (blood 20, bed 5, equipment 5, operating room 3). The origin's own stock left two of
the four needs short, so the search returned **2 short needs and 98 candidate hospital entries** each time.

## Method

- **Database:** a scratch SQLite file outside the repository, migrated and seeded with `seed_demo --hospitals 50`
  (default seed 7). Seeding took about 2 seconds.
- **Server:** `gunicorn config.wsgi:application` with its default single synchronous worker. `render.yaml` sets no
  worker count. Bound to `127.0.0.1:8765`. `DEBUG` was on, the local default. No proxy in front.
- **Client:** `scripts/load_test_search.py`, standard library only. It signs in as the default demo nurse, creates one
  case, runs 20 untimed warm-up GETs, then 200 timed GETs at each concurrency level. Each client waits for its reply
  before sending the next request.
- **Timing:** wall time on the client, from sending the request to reading the whole body. Percentiles are
  nearest-rank. Every timed request is a plain GET, so the search's own release sweep runs each time, as it does in
  production.
- **Versions:** Python 3.14.7, Django 6.0.10, Django REST Framework 3.18.1, gunicorn 26.2.0, SQLite 3.53.4.
- **Hardware:** Apple M1, 8 cores, 8 GB RAM, macOS 27.2.1.

## Exact command

Run from the repository root, with the backend's Python environment (`pip install -r backend/requirements-dev.txt`):

```bash
export DATABASE_URL=sqlite:///<scratch>/loadtest.sqlite3
python backend/manage.py migrate
python backend/manage.py seed_demo --hospitals 50
(cd backend && gunicorn config.wsgi:application --bind 127.0.0.1:8765)
python3 scripts/load_test_search.py --base-url http://127.0.0.1:8765 --requests 200 --warmup 20 --concurrency 1 5
```

`<scratch>` is any directory outside the repository. The script exits 1 if any request fails.

## Why the numbers look like this

- **Query count.** The search makes 9 queries per request, the same at 3 hospitals as at 10
  (`apps/matching/tests/test_candidates_scale.py`). No query runs per hospital.
- **Server work.** In-process on this data (no HTTP), the search has a p50 of 5.8 ms and a p95 of 7.6 ms over 60
  runs. Over HTTP, run sequentially, the candidates endpoint has a p50 of 8.7 ms and a p95 of 12.1 ms. A DB-free
  endpoint (`/api/health/`) takes 1.6 ms at p50, and a session endpoint (`/api/auth/me/`) takes 2.1 ms. So the search
  itself is about 6 ms of the server's time, and the rest is HTTP and Django.
- **Concurrency 5.** Five clients share one worker, so each request waits for the four ahead of it. That gives a p50
  about five times the single-client service time (about 9 ms each). More workers would lower these numbers; the
  query count would not change them.
- **No cheap fix.** The query count is already flat, and the time is spent in the worker, not in a query. Nothing
  was changed in the search. If a target is set later, the levers are the worker count and the database, not the
  queries. Spec Q4 asks for a record only, and no target has been set.

## Caveats

- **SQLite, not Postgres.** No Postgres or Docker runs on the build machine. The spec asks for Postgres 17 (Q2),
  and the user allowed SQLite when Postgres is unavailable. Absolute numbers on Postgres will differ: SQLite here is in a
  single file on a laptop disk, and Postgres has its own locking and I/O. **Open item:** run the exact command above
  against a Postgres 17 `DATABASE_URL` (from `docker-compose.yml`) before the B15 report.
- **Laptop, not a server, and no network.** The client and server share a machine, so network time is zero. Render's
  free tier adds network latency and runs on different hardware.
- **DEBUG was on.** Production runs with `DJANGO_DEBUG=false`. That changes only logging and query capture.
- **Shared machine.** Other processes ran on the machine during the session, including another test run (observed
  once, at 99% of a core). Load averages during runs B and C were about 2.7 on 8 cores. Run A's load was not recorded.
- **Staging was not tested.** Q2 excludes it: it is shared, it sleeps, and seeding it would change the demo network.
