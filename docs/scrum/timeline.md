# Release Plan & Timeline

**Start:** Saturday 3 Oct 2026 · **Final demo:** early December 2026 (exact date TBC) · **Sprint length:** 1 week (Sat → Fri)
Ceremonies (review + retro + planning) every **Friday at 22:00 PKT**.

This is a **forecast**. It gets re-checked every Friday against actual velocity. MVP scope follows the
WBS: blood, beds, equipment, operating rooms, emergency requests, matching, transfers, ambulances,
notifications, dashboards and audit. Items marked *(Secondary)* in the WBS are stretch goals.

```mermaid
gantt
    title Hospital Care: 9 one-week sprints
    dateFormat  YYYY-MM-DD
    axisFormat  %d %b
    section Foundation
    S1 Discovery & foundation            :s1, 2026-10-03, 7d
    S2 Access & hospital network         :s2, after s1, 7d
    section Resources
    S3 Blood inventory & donors          :s3, after s2, 7d
    S4 Beds, equipment, operating rooms  :s4, after s3, 7d
    section Emergency workflow
    S5 Emergency requests                :s5, after s4, 7d
    S6 Matching engine                   :s6, after s5, 7d
    S7 Reservation & transfers           :s7, after s6, 7d
    section Visibility & release
    S8 Ambulances, notifications, dashboards, audit :s8, after s7, 7d
    S9 Hardening & final demo            :crit, s9, after s8, 7d
```

| Sprint | Dates | Goal | Planned pts | Key outcome to demo on Friday |
|---|---|---|---|---|
| 1 | 3 Oct – 9 Oct | Discovery & foundation | 27 | Repo/CI live, ERD and wireframes, a user can log in |
| 2 | 10 Oct – 16 Oct | Access & hospital network | 32 | Roles enforced, 3 seeded hospitals, audit log working |
| 3 | 17 Oct – 23 Oct | Blood inventory & donors | 24 | Unit moves from collection → tested → available → expired |
| 4 | 24 Oct – 30 Oct | Hospital resources | 25 | Beds/equipment/OR registered, OR booking prevents clashes |
| 5 | 31 Oct – 6 Nov | Emergency requests | 31 | Case created with blood + bed requirements and tracked |
| 6 | 7 Nov – 13 Nov | Matching engine | 32 | Ranked, explained candidates across hospitals |
| 7 | 14 Nov – 20 Nov | Reservation & transfers | 34 | **Core MVP scenario**: reserve → transfer → receive |
| 8 | 21 Nov – 27 Nov | Ambulances, notifications, dashboards, audit | 29 | City command centre, live notifications |
| 9 | 28 Nov – 4 Dec | Hardening & final demo | 14 + stretch | E2E test green, stable staging, final report |

## Milestones that matter

- **End of Sprint 2 (16 Oct):** platform foundation done. If RBAC or the shared resource model slip, every later sprint slips too, so they get top priority.
- **End of Sprint 4 (30 Oct): mid-point check.** All resource types exist. Compare velocity with the plan and cut scope now if needed, not later.
- **End of Sprint 7 (20 Nov):** core MVP scenario works end to end. **This is the minimum we must be able to demo.**
- **Sprint 9:** no new features unless the E2E scenario is green. Spare capacity goes to stretch items.

## Scope cut order (if velocity is lower than planned)

Cut from the bottom of this list first:

1. Secondary items: specialists (2.4), patient transfer (6.3), reports (7.3)
2. Donation appointments (3.1)
3. Multi-resource matching (5.2), falling back to single-resource ranking
4. Ambulance dispatch/trip tracking (6.2), keeping only the registry
5. OR scheduling (2.3), keeping only the registry
6. Distance/travel time (5.1), falling back to listing candidates without distance

**Never cut:** auth/RBAC, blood inventory, emergency request, matching, atomic reservation, transfer, audit.
These make up the MVP acceptance scenario in the proposal (§23).

## Velocity check

Filled in by bolt B00 (#2) from GitHub: **Committed** is the points on each sprint milestone (planned points in
brackets where they differ), **Completed** is the committed points merged to `main` by the sprint end (the Definition
of Done), and **Merged in window** is every point that reached `main` during the sprint, whichever sprint planned it.

| Sprint | Planned | Committed (milestone) | Completed in sprint | Merged in window | Notes |
|---|---|---|---|---|---|
| 1 | 27 | 43 | 3 | 0 | Milestone also held the beds (#23–#25) and UI stories (#72–#78); only #1 was merged by 9 Oct, the rest landed 19–20 Oct |
| 2 | 32 | 27 | 0 | 0 | Nothing merged to `main` in the window; Sprint 2 items landed in the 19 Oct integration (#81) |
| 3 | 24 | 24 | 24 | 90 | Integration #81–#86 (19–20 Oct) merged Sprints 1–3 together: 90 points reached `main` in this window |
| 4 | 25 | 14 | 0 | 0 | Nothing merged; equipment and operating rooms landed in integration #100 (17 Nov) |
| 5 | 31 | 31 | 0 | 0 | Nothing merged; emergency cases landed in #100 (17 Nov) |
| 6 | 32 | 32 | 0 | 0 | Only AIDLC docs merged (#91, #92); matching landed in #100 (17 Nov) |
| 7 | 34 | 34 | 34 | 111 | #100 and #102 merged Sprints 4–7 together: 111 points reached `main` in this window |
| 8 | 29 | | | | In progress |
| 9 | 14 | | | |  |

**Average merged per sprint, Sprints 1–7:** 201 points / 7 ≈ 29 (plus #1, 3 points, merged at kickoff on 2 Oct), close to the ≈ 27 the plan needs. The problem
was not throughput but timing: work was integrated in two big batches (19 Oct and 17 Nov) instead of each sprint,
so five sprint reviews had nothing new on `main` to demo. See the Sprint 2–7 retrospectives.
