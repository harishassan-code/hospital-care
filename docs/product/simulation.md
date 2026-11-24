# The live city simulation (B21)

Staging has no real patients, so the network runs a simulation of one: patients arrive at emergency departments and
leave, beds are cleaned and turned over, blood is used and donated, theatres run their lists, staff clock in and out,
new emergency cases open and ambulances get held up. Every change goes through the same services, state machines,
row locks and audit log as a person's action. The CityCare admin runs it from the **Simulation** panel.

All patients are synthetic: a random tag (e.g. `ED-4821K`), an age band, a sex and a complaint category, never a name.
Bed boards show random initials, as the seed does.

## How it runs

| What | How |
|---|---|
| Where | `backend/apps/simulation` (engine, scenarios, controls), `apps/core/clock.py` (the city clock) |
| Switch | `SIMULATION_ENABLED`: on by default on Vercel, off in tests, CI and local Docker. Set it to `false` in the project's environment variables to stop the city (the clock then reads the real time) |
| Ticks | Vercel runs nothing in the background, so every open page asks `POST /api/simulation/tick/` every 20 seconds. The API runs at most one tick every 15 seconds, one at a time across all copies of the app (a lease on the state row). Nobody has the site open: the city sleeps, and catches up when someone comes back |
| Steps | The last two hours of any catch-up run in five-minute steps, patient by patient. Anything older runs hour by hour (a fast-forward hour: counts, stock, rotas, rooms and the history charts move in bulk, with one audit entry for the run). Gaps over 14 days are skipped |
| Locally | `SIMULATION_ENABLED=true python manage.py simulate` keeps it running; `simulate --minutes 90` runs the next 90 city minutes and stops |
| Reset | `seed_demo --reset` deletes the simulation's state, visits and events: the clock goes back to the real time |

## The city clock

Everything the app records and shows asks `apps.core.clock` for the time: cases, beds, blood expiry, waiting times,
rotas, "today", charts and the audit log. Sign-in sessions, sign-in limits and the cache keep Django's real clock, so a
fast-forward never signs anyone out. Audit entries keep the real time (`recorded_at`) beside the city time (`at`).

Every API response carries the clock (`X-City-Time`, `X-City-Mode`, `X-City-Speed`); the site reads it there, so all
screens agree. While the clock isn't simply the real time, every staff page shows **Simulated time** in the top bar.

The clock only moves forward. Pausing stops it; a speed change runs it faster or slower from where it is; a
fast-forward runs the city through the time it skips. **Catch up** appears when the clock is behind the real one.

## The Simulation panel (CityCare admin)

Sign in as `network@demo.citycare.pk` (an admin with no hospital). A hospital's admin can't open it.

| Control | Effect |
|---|---|
| Pause / Resume | Stops or restarts the clock and the city |
| Speed | ½×, real time (1×), 2×, 5×, 10× or 60× |
| Fast-forward | +30 minutes, 1 hour, 1 day, 1 week or 2 weeks, with a progress bar. On the free plan a day takes about 10 seconds and two weeks a few minutes |
| Scenario | Regular day, Flu season or Slow day: the ranges below |
| Mass-casualty event | For 1 to 3 hours, waves of trauma patients at the three general hospitals nearest a random city district |
| What happened lately | The last 50 events: triage 1 arrivals, diversions, blood groups at zero, emergency theatre cases, new cases, delays, absences, control changes |

## Scenarios: ranges, not scripts

Nothing happens on a fixed schedule or with fixed numbers. Each rate has a range in its scenario; the engine draws a
fresh value inside it on every tick, and each event is a random draw at that rate. The ranges are the buffers: values
never leave them. Capacity (beds, staff, rooms, stock) then limits what can happen, so a full department diverts
ambulances the way a real one does. The values live in `backend/apps/simulation/profiles.py`.

| Rate | Regular day | Flu season | Slow day |
|---|---|---|---|
| Emergency arrivals (× the hospital's usual) | 0.9–1.1 | 1.12–1.25 | 0.6–0.8 |
| Triage 1 / 2 / 3 / 4 / 5 (shares) | 0.5–1.5% / 8–12% / 35–45% / 25–33% / 10–18% | 0.8–2% / 10–15% / 40–50% / 22–30% / 6–12% | 0.4–1.2% / 7–10% / 30–40% / 30–38% / 15–22% |
| Breathing problems among complaints | 10–14% | 30–40% | 10–14% |
| Admitted from the department (triage 1 / 2 / 3) | 70% / 45% / 15% | 75% / 50% / 19% | 70% / 45% / 15% |
| Transferred to another hospital | 1–2.5% | 2–4% | 1–2% |
| Leave unseen (triage 4–5 after an hour, per hour) | 3–6% | 5–9% | 2–4% |
| Length of a ward stay (× usual) | 0.9–1.1 | 1.2–1.4 | 0.85–1.0 |
| Ward occupancy planned admissions fill to | 82–90% | 86–92% | 72–80% |
| Red-cell use (× usual) | 0.85–1.15 | 0.9–1.1 | 0.6–0.8 |
| Donations (× usual) | 0.9–1.15 | 0.65–0.85 | 0.7–0.9 |
| Theatre cases cancelled | 6–12% | 12–20% | 4–8% |
| Emergency theatre cases (per room per day) | 0.15–0.35 | 0.15–0.3 | 0.08–0.2 |
| Shifts nobody turns up for / started late | 1.5–3.5% / 4–8% | 4–8% / 5–10% | 1–2.5% / 3–6% |
| New emergency cases (network, per day) | 3–6 | 4–8 | 1–3 |
| Ambulance trip held up (per 5 minutes) | 2–5% | 3–6% | 1–3% |

**Mass-casualty event** (on top of the season, at the three nearest general hospitals, nearest first): 12–30 extra
arrivals an hour each, triage 1 20–30% and triage 2 35–45%, all injuries; O-negative and O-positive red-cell use 3–5
times usual; 0.3–0.6 emergency theatre cases an hour; 2–4 extra critical cases an hour. Children's and women's hospitals
aren't sent a trauma wave.

Daily rhythms come from the history (B20, [demo-data.md](demo-data.md)): arrivals lowest 03:00–05:00 and highest late
morning and evening, busier on Mondays; blood used mostly by day; donations 09:00–19:00; discharges 09:00–17:00, most
before 14:00; planned admissions 10:00–21:00; theatre lists 08:00–17:00, none on Sundays.

## The emergency department

- **Treatment.** Patients are seen in triage order, then by arrival; triage 1 at once. Minutes in the department once
  seen: triage 1 150–300, 2 120–240, 3 90–180, 4 45–120, 5 20–60 (flu: 5–10% longer). Triage 1–3 need an emergency bed;
  minor complaints can be seen in a chair, and a fast-track place (one per 40 usual arrivals a day) sees them when the
  doctors are busy.
- **Leaving.** Home, a ward bed (intensive care for most triage 1, isolation for breathing problems when there is one,
  a ward that takes the patient's age and sex), another hospital, or unseen. An admission with no ward bed free waits in
  its emergency bed ("boarding"), which slows the department: the exit block real departments know.
- **Beds.** An emergency bed is cleaned for 10–30 minutes after a patient leaves; a ward bed 30–90 minutes.
- **Waiting time.** Recomputed on every step (`apps/emergencies/wait.py`). A department is staffed to see 1.55 times its
  usual hourly arrivals; it runs at that pace with the doctors and nurses its rota plans, slower with fewer (an absent
  doctor, a late nurse; with nobody clocked in a ward doctor covers at half pace), and never faster than its free
  emergency beds allow. A new triage 3 patient waits behind everyone of the same or higher priority, plus the arrivals
  of the next half hour it can't absorb. The staff emergency page lists the factors and the minutes each added.
- **Status.** Very busy from an hour's wait or one urgent patient waiting per bed; not accepting ambulances from 2½
  hours or 1½ per bed (minor complaints count a quarter). A status a person set is left alone for 30 minutes.

## What it never touches

- A bed, room or blood unit held or allocated for a case (a reservation), or a case or transfer a person created or acted
  on. Its own cases that nobody picks up are met locally and cancelled after 1–3 hours.
- The scripted demo's stock: the scenario's O-negative red cells at its three hospitals (`BloodUnit.demo_stock`, set by
  `seed_demo`). The simulation neither uses nor adds to them. Blood still expires on its date, so after a fast-forward of
  more than about six days run `seed_demo --reset` before the scripted demo.
- A bed a nurse admitted by hand (no planned discharge date).

## Alerts

Only what a person must act on, at most one of each kind per hospital per 30 minutes of city time (and per 2 real
minutes): a triage 1 arrival (emergencies staff), the department not accepting ambulances (emergencies staff), a blood
group's red cells at zero (blood bank staff). New critical cases alert as any case does.

## Data kept

Emergency visits, simulation events and the hourly figures are pruned after 14 days of city time, shifts after 21. The
audit log is append-only and keeps everything; filter it by `simulation@system.citycare.invalid` to see or hide the
simulation's entries.
