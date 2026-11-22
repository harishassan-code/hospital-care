# Performance report: candidate search (#58)

**Script:** `scripts/load_test_search.py` (standard library only). It signs in as the demo doctor, opens one
synthetic case needing 4 O− red cells, an ICU bed and a ventilator, then calls
`GET /api/emergencies/<ref>/candidates/` N times and prints p50 / p95 / max.

**Target (agreed in the B13 spec):** p95 under 500 ms with 50 hospitals, on staging.

## Results

| Date | Environment | Hospitals | Requests | p50 | p95 | max |
|---|---|---|---|---|---|---|
| 2026-11-22 | Local laptop: `runserver` (DEBUG), **SQLite file inside a OneDrive-synced folder**, Windows | 50 (`seed_demo --hospitals 50`) | 200 | 2117 ms | 2155 ms | 2254 ms |
| _to do_ | Staging: Render + PostgreSQL | 50 | 200 | | | |

## Reading the local number

The local run **misses the target** and should not be quoted as the system's latency:

- Every candidates GET first runs the request-time sweeps (`release_expired`, `escalate_overdue`; see their
  `ponytail:` notes). Each is a write transaction, and SQLite in a OneDrive-synced folder makes every write slow.
- The response is small (≈ 800 bytes) and the search's query count is pinned by
  `apps/matching/tests/test_candidates_performance.py`, so the search itself isn't the cost.

**Next step for the final report:** run the script against staging after seeding 50 hospitals there, and fill in
the second row. If p95 is still over 500 ms, move the two sweeps to a scheduled job (the upgrade path their
`ponytail:` notes already name) and measure again.
