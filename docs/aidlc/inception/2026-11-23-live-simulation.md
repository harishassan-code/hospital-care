# Inception Spec: Live city simulation on staging

**Date:** 2026-11-23
**Author:** Haris Hassan (Claude, drafted for review)
**Bolt:** [B21](../bolts/B21-live-simulation.md)
**Related backlog item:** the account owner's request of 23 Nov (a GitHub issue is opened when this is approved)

## Problem

Staging has no real patients, so nothing on it ever changes unless someone clicks. A real city network is never
still: patients arrive, beds turn over, blood is used and donated, theatres run their lists, shifts change. Without
that, the dashboards, alerts and waiting times can't show what they are for, and a demo looks like a slideshow.

For: the Product Owner and demo audiences (a living system), the team (realistic load on every page and alert), and
each role in the demo (something to act on).

## User stories

- As a nurse, I want an emergency bed to become free after a low-priority patient is treated and discharged, and
  then be cleaned, so that the bed board reflects the department.
- As emergency staff, I want new patients to arrive in random order and priority, so that the queue behaves like a
  real one.
- As blood bank staff, I want units to be used and donated, so that stock, expiry and low-stock alerts move.
- As theatre staff, I want rooms booked, cancelled, in use, cleaned and available again, so that the schedule is live.
- As a manager, I want doctors and nurses to clock in and out, so that I see who is on duty.
- As anyone checking a hospital, I want new emergencies, delays and waiting times that follow from what is happening,
  so that the numbers mean something.
- As an admin, I want to pause, resume and see what the simulation did, so that it never gets in the way.

## Acceptance criteria

**What happens** (rates scaled to each hospital's size, with daily rhythms; values in `docs/product/simulation.md`):
- [ ] **Emergency department queue** (new `ErVisit`, per hospital): patients arrive at random with a triage level
      1–5 (1 = resuscitation), a random tag, an age band, sex and a complaint category, never a name. They wait, are
      seen in triage order (then by arrival), are treated in an emergency bed (occupied), and leave as discharged,
      admitted (moved to a ward bed), transferred or left without being seen. The emergency bed then goes to
      cleaning (10–30 min) and back to free.
- [ ] **Wards:** admissions from the emergency department and planned admissions; discharges, mostly late morning;
      cleaning (30–90 min) before a bed is free again.
- [ ] **Waiting time:** each hospital's estimate is recomputed on every tick from the patients waiting by triage
      level, emergency doctors and nurses on duty, free emergency beds, arrivals in the last hour and admitted
      patients still waiting for a ward bed. It sets `EmergencyStatus` (wait, number waiting, and accepting / very
      busy / not accepting ambulances by thresholds). The staff emergency page shows which factors moved it.
- [ ] **Blood:** units issued every day by group, roughly in proportion to hospital size and the donor shares;
      donations arrive as quarantined units, pass their screening tests a few hours later and become available
      (about 1 in 50 fails and is discarded); expired units are processed. Existing low-stock and expiry alerts fire
      from these changes.
- [ ] **Operating rooms:** bookings added for the coming days; about 1 in 10 cancelled; a booked case starts (in use),
      ends (cleaning, 20–40 min) and the room is available; now and then an emergency case takes a free room.
- [ ] **Staff:** each shift clocks in within about 10 minutes of its start and out within about 20 minutes after its
      end; now and then someone is late or absent, which feeds into the waiting time.
- [ ] **Emergencies and delays:** new emergency cases (`EmergencyRequest` with needs) at a low, realistic rate across
      the network, created through the existing service so matching, holds and transfers work on them; ambulance
      trips that are under way sometimes slip their arrival time.
- [ ] **History:** hourly `MetricSnapshot` rows keep being written (B20), so the charts continue.

**How it runs:**
- [ ] It runs where Vercel can run it: the staff pages' 30-second refresh and the public pages call a tick service
      that brings the simulation from its last tick up to now. At most one tick runs at a time (a row lock), at most
      one every 15 seconds, and a tick catches up at most 2 hours, in steps (Q1).
- [ ] Locally `python manage.py simulate` runs it in a loop, and `simulate --minutes N` advances it once.
- [ ] Off unless `SIMULATION_ENABLED=true` (set on staging; off in tests, CI and local Docker by default).
- [ ] An admin can pause and resume it and see its last 50 events in the Command centre, with a "Run the next 30
      minutes now" button for demos.

**Safety and rules:**
- [ ] Every change goes through the same services, state machines and `transaction.atomic()` with
      `select_for_update()` as a person's would, and is audit-logged with the actor **CityCare simulation**, a system
      user that can't sign in. The audit page can filter by it.
- [ ] It never touches a resource held by a reservation or a transfer, a case or transfer a person created or acted
      on, or the stock the demo script relies on (flagged by `seed_demo`). A test proves each of these.
- [ ] Alerts only for what a person must act on (a level 1 arrival, a department not accepting ambulances, a blood
      group at zero), at most one of each kind per hospital per 30 minutes, so they never flood.
- [ ] Old data is pruned on each tick: emergency visits and simulation events after 14 days, snapshots after 14 days.
- [ ] Privacy as in B23: simulated patients have no names, and their visit details reach only the staff allowed to
      see them.

## Design

- New `apps/simulation`: `SimulationState` (single row: enabled, paused, last tick, random seed), `SimEvent` (what
  happened, for the Command centre list), `engine.py` (one function per kind of event, each a small transaction
  through the owning app's services), `tick.py` (catch-up loop, lock, pruning), the `simulate` command.
- `apps/emergencies`: `ErVisit` model and its services (`arrive`, `start_treatment`, `discharge`, `admit`,
  `transfer`, `left_unseen`), `estimate_wait(hospital)`; endpoints for the staff queue (B22 builds the page).
- `apps/staffing` (from B20): `clock_in`/`clock_out` services and a "who's on duty" query.
- The tick is triggered by `POST /api/simulation/tick/` (no body, cheap when it's too early), called by the staff
  refresh and the public pages, and by the admin's run button (`POST /api/simulation/run/`, admin only).
- Rates and thresholds live in one settings module so they can be tuned without code changes elsewhere.

## Non-goals

- Charts and the new pages themselves (B22).
- Running when nobody has the site open (Q1).
- Clinical accuracy beyond plausible rates; this is a simulation for demos, not a model of care.

## Open questions

Proposed answers; the account owner confirms them at sign-off:

1. **How does it run on Vercel?** *Proposed:* on request, as above. Vercel's free plan has no background workers and
   runs scheduled jobs at most once a day, so a ticking clock isn't available. The effect: the city "sleeps" while
   nobody has the site open and catches up (up to 2 hours) when someone comes back. During a demo the pages are open,
   so it is live.
2. **Real time or faster?** *Proposed:* real time, so times on screen match the clock. For demos, the admin's "Run the
   next 30 minutes now" makes things happen on cue.
3. **The scripted demo and the e2e test?** *Proposed:* the simulation leaves the demo's stock and anything a person
   is working on alone, so it can stay on during the demo (it's part of the show). The e2e test and CI run with it
   off.
4. **How much does it keep?** *Proposed:* 14 days of visits, events and snapshots, pruned on each tick, which keeps the
   free database small.
5. **Alerts?** *Proposed:* only the three kinds above, rate-limited, so staff alerts stay meaningful.

## Amendment at sign-off, 23 Nov

The account owner approved this spec with two changes, which replace Q2 and add to the criteria above:

1. **Scenarios, not scripts.** Nothing happens on a fixed schedule or with fixed numbers. Each rate (arrivals, triage
   mix, length of stay, discharges, blood use and donation, theatre cancellations, staff absence, new emergencies)
   comes from the active **scenario profile**, which gives it a range: the engine draws a fresh random value inside
   that range on every tick. The bounds are the buffers: values never leave them, and capacity (beds, rooms, staff,
   stock) caps what can happen, so a full department diverts ambulances the way a real one does. Profiles:
   - **Regular day**: the everyday rhythm.
   - **Flu season**: more arrivals, many respiratory, longer stays, more intensive care, more staff off sick.
   - **Mass-casualty event**: switched on by the admin; for 1 to 3 hours, waves of trauma patients (mostly triage 1
     and 2) arrive at the hospitals nearest a random incident site, with a surge in O-negative and O-positive blood use
     and emergency theatre cases, then the city settles back to its season.
   - **Slow day**: fewer arrivals and planned cases, like a public holiday.
   Profiles and their ranges live in one settings module and `docs/product/simulation.md`.
2. **City clock and time controls.** The app runs on a **city clock**: the real clock plus an offset, at a speed.
   The **CityCare admin** (the admin with no hospital) gets a **Simulation** panel on the demo site to play in real
   time, pause, slow down or speed up (½×, 1×, 2×, 5×, 10×, 60×), fast-forward by an hour, a day, a week or two weeks,
   pick the scenario, set off a mass-casualty event, and see the latest events. Everything the app records and shows
   (cases, beds, blood expiry, waits, rosters, "today", charts) uses the city clock, and the frontend reads the city
   time from the API so screens agree. Sign-in sessions, sign-in limits and security headers keep the real clock, so
   a fast-forward never signs anyone out. Audit entries keep the real time beside the city time, so the trail stays
   truthful. While the clock isn't at real time, every signed-in page shows an indicator (for example "Simulated
   time, 10×").
   - A fast-forward simulates the last few hours event by event and earlier time hour by hour (stock, counts and the
     history snapshots), in steps driven by the panel's polling, with a progress bar, so it fits Vercel's request
     time limit.
   - Only the CityCare admin can change the clock. Hospital admins and staff can't.

## Approval

- [x] Approved by: Haris Hassan (`harishassan-code`, account owner) on 2026-11-23, with the amendment above
