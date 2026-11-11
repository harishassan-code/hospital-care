# Inception Spec: Distance and estimated travel time

**Date:** 2026-11-11
**Author:** Claude, drafted for review
**Related backlog item:** [#39 Distance and estimated travel time](https://github.com/harishassan-code/hospital-care/issues/39) (Epic E5, Sprint 6, 3 pts)

## Problem

The matching engine (Epic E5) needs to compare candidate hospitals by how far they are from the
hospital requesting a resource. Right now `Hospital` already stores `latitude`/`longitude`
(`backend/apps/hospitals/models.py`), but nothing computes a distance or a travel-time estimate
from them. Coordinators have no way to tell "nearer" apart from "farther" when results come back.

## User stories

- As an emergency coordinator, I want to see the straight-line distance between my hospital and a
  candidate hospital, so that I can prefer nearer sources.
- As an emergency coordinator, I want an approximate travel time for that distance, so that I can
  judge how long a transfer would realistically take.

## Acceptance criteria

- [ ] Given two hospitals' coordinates, the system computes the straight-line (Haversine) distance
      in kilometres.
- [ ] Given a distance, the system estimates travel time in minutes from a configurable average
      city driving speed (simulated — no real routing/traffic API).
- [ ] Both are exposed as a small, reusable utility the matching engine can call once scoring
      (#40) and candidate search (#41/#42) are built.
- [ ] Unit tests cover: zero distance (same point), a known real-world distance pair (sanity
      check against a published value), and the travel-time conversion.

## Non-goals

- No real road-routing or live traffic (explicitly "simulated" per the backlog item).
- No API endpoint or UI yet — the scoring model (#40) and ranked results (#41) that will consume
  this don't exist yet either, so this unit stays a backend utility + tests. Wiring it into an
  endpoint is a later unit once #40/#41 land.
- No changes to the `Hospital` model (coordinates already exist).

## Open questions

- Average city driving speed to assume for the simulated estimate — defaulting to 40 km/h (typical
  dense-city average) unless a different figure is preferred.

## Approval

- [x] Approved by: KingU on 2026-11-11
