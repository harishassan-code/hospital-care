# Candidate search load test (B13)

**Bolt:** [B13](../aidlc/bolts/B13-security-performance.md) · **Issue:** [#58](https://github.com/harishassan-code/hospital-care/issues/58)
**Date:** 2026-11-22 (PostgreSQL), 2026-11-18 (SQLite) · **Code:** `main` at `a81656e` (PostgreSQL run); the
script is from `ce9ae8c`, `seed_demo --hospitals` from `b7d9e82`
**Script:** [`scripts/load_test_search.py`](../../scripts/load_test_search.py) · **Spec:** [Q1 to Q4](../aidlc/inception/2026-11-18-security-performance.md)

## Result (PostgreSQL): the figure for the final report

Candidate search, `GET /api/emergencies/<reference>/candidates/`, against a 50-hospital network, one synchronous
gunicorn worker (as `render.yaml` runs it), **PostgreSQL 16**. Three runs, a few minutes apart, on an otherwise idle
machine. Every one of the 1,200 timed requests succeeded.

| Run | Concurrency | p50 ms | **p95 ms** | p99 ms | max ms | Requests | Errors | Load average before / after (4 cores) |
|---|---|---|---|---|---|---|---|---|
| A | 1 | 16.1 | **26.0** | 29.2 | 97.6 | 200 | 0 | 0.02 / 0.10 |
| A | 5 | 83.4 | **107.6** | 166.8 | 171.1 | 200 | 0 | (same run) |
| B | 1 | 15.9 | **25.4** | 31.1 | 81.9 | 200 | 0 | 0.15 / 0.28 |
| B | 5 | 85.5 | **139.1** | 165.5 | 175.8 | 200 | 0 | (same run) |
| C | 1 | 16.0 | **25.9** | 28.0 | 101.6 | 200 | 0 | 0.20 / 0.32 |
| C | 5 | 83.6 | **108.0** | 157.8 | 160.4 | 200 | 0 | (same run) |

**Recorded p95: about 26 ms at concurrency 1 (25.4 to 26.0 over three runs), and 108 to 139 ms at concurrency 5.**
Each run's case returned **2 short needs and 98 candidate hospital entries**, as in the SQLite run.

**Same machine, SQLite, for comparison** (same command, `DATABASE_URL` pointing at a SQLite file, two runs):
p95 17.4 and 17.9 ms at concurrency 1, 68.0 and 79.7 ms at concurrency 5. So on the same hardware PostgreSQL is
about 1.45 times SQLite. A search makes **10 queries** (the same at any network size, see *Why the numbers look like
this*), each a round trip to a separate database server; SQLite answers in-process. In-process (no HTTP), the search
takes a p50 of 10.8 ms on PostgreSQL and 8.4 ms on SQLite. The extra time is those round trips, not slow queries:
each query finishes in under a millisecond.

### Dataset (PostgreSQL)

After `seed_demo --hospitals 50`, before the runs: 50 hospitals (3 named, 47 synthetic), 153 wards, 1,668 beds (238
free), 1,104 blood units (1,046 available), 60 donors, 6 donation appointments, 113 pieces of equipment, 150
operating rooms, 300 bookings, 23 medicines, 7 ambulances, 14 specialists with 98 on-call windows, 6 users. Emergency
cases: 0 before, 3 after (one per run). Seeding took 3.3 seconds. Since the SQLite run, #107 marks 3 surplus O− units
issued (1,046 available instead of 1,049), and #104 and #109 add the ambulances and specialists; the search reads
none of those.

### Method and versions (PostgreSQL)

As in *Method* below, with these differences: the database is a scratch PostgreSQL 16.15 cluster on the same
machine (TCP on `127.0.0.1`), and the machine is a 4-core Intel Xeon cloud VM with 15 GB RAM (Linux 6.18). Python
3.13.18, Django 6.0.10, DRF 3.18.1, psycopg 3.3.6, gunicorn 26.2.0. `DEBUG` on, the local default, as before.

```bash
export DATABASE_URL=postgres://hospitalcare@127.0.0.1:5433/hospitalcare
python backend/manage.py migrate
python backend/manage.py seed_demo --hospitals 50
(cd backend && gunicorn config.wsgi:application --bind 127.0.0.1:8765)
python3 scripts/load_test_search.py --base-url http://127.0.0.1:8765 --requests 200 --warmup 20 --concurrency 1 5
```

**PostgreSQL 16, not 17.** The spec asks for 17 (Q2), the version CI runs. 16 is what this machine has; the search
uses nothing that differs between the two. CI runs the whole test suite on 17.

## Earlier run: SQLite on a laptop (18 Nov)

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
Recorded p95 for this SQLite run: 12.5 ms at concurrency 1, and 49 to 51 ms at concurrency 5. It is superseded by
the PostgreSQL result above for the final report.

## Dataset (SQLite run)

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

(Written for the SQLite run; the PostgreSQL run differs only as noted above.)

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

- **Query count.** The search makes 10 queries per request (9 when it was first measured, before later PRs added
  case fields), the same at 3 hospitals as at 10 (`apps/matching/tests/test_candidates_scale.py`). No query runs per
  hospital.
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

- **SQLite run, then PostgreSQL.** The first run used SQLite because no Postgres ran on that machine. The open item
  it left (run the same command on Postgres before the B15 report) is done: see the PostgreSQL result at the top,
  with a same-machine SQLite comparison.
- **Laptop, not a server, and no network.** The client and server share a machine, so network time is zero. Render's
  free tier adds network latency and runs on different hardware.
- **DEBUG was on.** Production runs with `DJANGO_DEBUG=false`. That changes only logging and query capture.
- **Shared machine.** Other processes ran on the machine during the session, including another test run (observed
  once, at 99% of a core). Load averages during runs B and C were about 2.7 on 8 cores. Run A's load was not recorded.
- **Staging was not tested.** Q2 excludes it: it is shared, it sleeps, and seeding it would change the demo network.
