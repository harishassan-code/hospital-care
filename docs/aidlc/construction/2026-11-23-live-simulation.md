# Construction Plan: Live city simulation with time controls

**Spec:** [docs/aidlc/inception/2026-11-23-live-simulation.md](../inception/2026-11-23-live-simulation.md)
**Date:** 2026-11-23

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | The city clock: `apps/core/clock.py` (`now`, `localdate`, `at` for a step), used everywhere the app reads the time; `SIMULATION_ENABLED`; the clock headers on every API response; auto timestamps follow it, and the audit log keeps the real time beside it (`recorded_at`) | `apps/core/clock.py`, `apps/core/middleware.py`, `config/settings.py`, every app's models and services, migrations | Off: the real clock. On: speed, pause, fast-forward; a step's own time; sign-in keeps the real clock; headers only while on |
| 2 | Emergency visits (`ErVisit`, `VISIT_LIFECYCLE`, `visits.py`), the wait estimate and its factors (`wait.py`), bed placement services, clock-in services and rota extension, donations, metric levels | `apps/emergencies`, `apps/hospitals/services.py`, `apps/staffing/services.py`, `apps/blood/services.py`, `apps/metrics/services.py` | Through the engine tests below |
| 3 | The engine: scenario profiles with ranges, one module per area (emergency department, wards, blood, theatres, staff, cases and delays), the hour-by-hour fast-forward, daily rollover and pruning, the lease and the tick | `apps/simulation/` | Triage order; held beds, rooms and units untouched; boarding and admission; cleaning; planned discharges only; FIFO blood without demo stock; screening; rate-limited alerts; theatre cycle; clock-ins; a person's case left alone; pruning; three hours of the demo network |
| 4 | The CityCare admin: `IsNetworkAdmin`, the `simulation` module, the controls and their endpoints, the system account, the network admin's demo login, `seed_demo` flags demo stock and resets the simulation | `apps/accounts/permissions.py`, `apps/simulation/{controls,views,urls}.py`, `seed_demo.py` | Only the network admin; each control audited; bad values refused; the tick is open and cheap |
| 5 | The site: the clock store fed by the headers, the ticker, the Simulation panel, the "Simulated time" indicator, the wait factors on our emergency department | `frontend/src/lib/cityClock.ts`, `features/simulation/`, `pages/staff/SimulationPage.tsx`, `features/emergencies/`, `roles.ts`, `test/mockApi.ts` | The clock runs at its speed and stands still when paused; the indicator; the panel's controls, fast-forward progress, scenario, mass-casualty event and events; hidden from a hospital's admin; the factors list |
| 6 | Docs: the simulation guide with every range, API, access table, ERD, deployment, demo script | `docs/` | Board and deploy checks |

Refinements of the spec, settled while building:

- The waiting-time model sizes each department to 1.55 times its usual hourly arrivals at full staff. A flat
  "patients per doctor" left some departments idle and others overwhelmed, because rotas and arrivals aren't in the
  same proportion everywhere. A regular day was then run patient by patient for all nine departments: mostly accepting,
  some very busy at peaks, none diverting; flu season: widely very busy, the busiest diverting by evening; a slow day:
  quiet.
- Minor complaints have a small fast track, and diversion counts them at a quarter, as real departments do.
- A mass-casualty event goes to the nearest *general* hospitals; the children's and women's hospitals take their own
  patients.
- The clock never goes back. "Play in real time" is the 1× speed; **Catch up** brings a paused or slowed clock to the
  real time.

## Test plan

AGENTS.md checks, the deploy-config and board checks, and the e2e scenario against a fresh seed (with the simulation
off, as CI runs it). Calibration runs of a day per scenario on the seeded network, event by event.

## Review

The PR needs a reviewer's approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md).
