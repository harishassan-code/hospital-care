# Sprint 8 Review

**Date:** Fri 27 Nov, 22:00 PKT · **Attendees:** _at the review_ · **Product Owner present:** _at the review_

> **Prepared record.** The facts below were filled in on 23 Nov 2026 from the GitHub history (milestone, issue close
> dates, points from `scripts/backlog.py`, merged pull requests). The review hasn't happened yet: who demoed,
> acceptance, Product Owner feedback and backlog changes are left for the team to fill in at the review. Before then,
> re-check the PR list and metrics for anything merged after 23 Nov.

## Sprint goal
> Ambulances, notifications, dashboards, audit: a city command centre and live notifications

**Met?** _at the review_. On 23 Nov every committed item was on `main`.

## Demoed increment

| Issue | Title | Points | On `main` | Demoed by | Accepted? | Feedback |
|---|---|---|---|---|---|---|
| [#50](https://github.com/harishassan-code/hospital-care/issues/50) | Ambulance registry | 3 | 22 Nov (#104) | | | |
| [#51](https://github.com/harishassan-code/hospital-care/issues/51) | Ambulance dispatch and trip tracking | 5 | 22 Nov (#104) | | | |
| [#52](https://github.com/harishassan-code/hospital-care/issues/52) | Notification service | 5 | 22 Nov (#104) | | | |
| [#53](https://github.com/harishassan-code/hospital-care/issues/53) | In-app alerts UI | 3 | 22 Nov (#104) | | | |
| [#54](https://github.com/harishassan-code/hospital-care/issues/54) | Hospital dashboard | 5 | 22 Nov (#104) | | | |
| [#55](https://github.com/harishassan-code/hospital-care/issues/55) | City command centre dashboard | 5 | 22 Nov (#104) | | | |
| [#56](https://github.com/harishassan-code/hospital-care/issues/56) | Audit search and export | 3 | 22 Nov (#104) | | | |

Also on `main` and available to demo:

| Issue | Title | Points | On `main` |
|---|---|---|---|
| #61, #62 | Specialists: doctor profiles, on-call windows, "Available now" (stretch) | 6 | 22 Nov (#109) |
| #63–#65 | Patient transfer: need check, destination, arrival (stretch) | 11 | 22 Nov (#106) |
| #66, #67 | Operational reports with CSV and PDF export (stretch) | 5 | 22 Nov (#112, #119) |
| [#57](https://github.com/harishassan-code/hospital-care/issues/57) | End-to-end MVP scenario: every step of §23 in one browser test, green on three consecutive CI runs (Sprint 9) | 5 | 22 Nov (#107, #124, #125) |
| [#122](https://github.com/harishassan-code/hospital-care/issues/122), [#123](https://github.com/harishassan-code/hospital-care/issues/123) | Security review findings F5 and F7 fixed (bugs) | – | 23 Nov (#128) |
| – | Clinical Calm redesign, CityCare name, light/dark toggle | – | 23 Nov (#126, #128) |

## Pull requests merged during the sprint (to 23 Nov)

- [#104](https://github.com/harishassan-code/hospital-care/pull/104) Sprint 8: ambulances, notifications and alerts, dashboards, audit search and donors page (#50–#56) (@codewithalphadotcom, 22 Nov)
- [#106](https://github.com/harishassan-code/hospital-care/pull/106) feat(emergencies): patient transfer: need check, destination and arrival (B17, #63, #64, #65) (@codewithalphadotcom, 22 Nov)
- [#107](https://github.com/harishassan-code/hospital-care/pull/107) test(e2e): Playwright MVP acceptance scenario (B12, #57) (@codewithalphadotcom, 22 Nov)
- [#108](https://github.com/harishassan-code/hospital-care/pull/108) fix(security): deploy hardening, cross-hospital access fixes, sign-in throttle, search load test (B13, #58) (@codewithalphadotcom, 22 Nov)
- [#109](https://github.com/harishassan-code/hospital-care/pull/109) feat(specialists): staff directory with on-call windows and "Available now" filter (B16, #61, #62) (@codewithalphadotcom, 22 Nov)
- [#111](https://github.com/harishassan-code/hospital-care/pull/111) feat(staging): demo script, smoke check and staging docs; sign B14, B15, B18 specs (B14, #59, #69) (@Hassan27521, 22 Nov)
- [#112](https://github.com/harishassan-code/hospital-care/pull/112) feat(reports): operational reports with CSV and PDF export (B18, #66, #67) (@Hassan27521, 22 Nov)
- [#114](https://github.com/harishassan-code/hospital-care/pull/114) UAT checklist and API permission coverage test (#58) (@Kabir-Raj-01, 22 Nov)
- [#115](https://github.com/harishassan-code/hospital-care/pull/115) fix(tests): flaky 403 polling test in NotificationFeed (main's red frontend job) (@Kabir-Raj-01, 22 Nov)
- [#116](https://github.com/harishassan-code/hospital-care/pull/116) B00: Scrum records for Sprints 1–7, velocity and deliverables index (#2) (@Kabir-Raj-01, 22 Nov)
- [#117](https://github.com/harishassan-code/hospital-care/pull/117) docs: user manual, risk register, and handover note with future roadmap (@Kabir-Raj-01, 22 Nov)
- [#119](https://github.com/harishassan-code/hospital-care/pull/119) fix(reports): show blood component labels in CSV/PDF wastage, as the page does (B18, #67) (@Kabir-Raj-01, 22 Nov)
- [#120](https://github.com/harishassan-code/hospital-care/pull/120) fix(staff): don't update workspace data after it unmounts (flaky 'window is not defined' in CI) (@Kabir-Raj-01, 22 Nov)
- [#121](https://github.com/harishassan-code/hospital-care/pull/121) Final fixes: demo reset after a rehearsal, bolt owners, merged bolts marked Done (B14, #59) (@harishassan-code, 22 Nov)
- [#124](https://github.com/harishassan-code/hospital-care/pull/124) Final stretch: e2e covers all of §23, PostgreSQL load test, security review, final report and slides (B12, B13, B15) (@harishassan-code, 22 Nov)
- [#125](https://github.com/harishassan-code/hospital-care/pull/125) B12 Done: e2e scenario green on three consecutive CI runs of one commit (B12, #57) (@harishassan-code, 22 Nov)
- [#126](https://github.com/harishassan-code/hospital-care/pull/126) Pre-staging sweep fixes and the Clinical Calm redesign (@harishassan-code, 23 Nov)
- [#127](https://github.com/harishassan-code/hospital-care/pull/127) fix(docker): new frontend packages arrive with `docker compose up --build` (@harishassan-code, 23 Nov)
- [#128](https://github.com/harishassan-code/hospital-care/pull/128) CityCare name, lighter type, light/dark toggle, more motion; closes #122 and #123 (@harishassan-code, 23 Nov)

## Metrics (as of 23 Nov)

| Committed | Completed (DoD met) | Points merged in this window (any sprint) | Bugs opened | Bugs closed | PRs merged |
|---|---|---|---|---|---|
| 29 | 29 | 56 | 2 (#122, #123) | 2 (#122, #123) | 19 |

Points merged in the window: the 29 committed, 22 stretch (#61–#67) and Sprint 9's #57 (5), closed 22 Nov. The code
for #58 and #59 is also on `main`, but those issues stay open until staging is live, so they aren't counted.

The [velocity table](../../scrum/timeline.md#velocity-check) still shows 51 merged (as of 22 Nov, before #57 closed).
After the review, put the final figure there and rebuild the charts, report and slides from it.

**Burndown:** _screenshot GitHub Project → Insights for this milestone at the review._ The release burndown rebuilt
from the record is in [final/charts/burndown.png](../final/charts/burndown.png).

## Not completed

None of the committed items. Open going into Sprint 9:

| Issue | Why | Action |
|---|---|---|
| [#58](https://github.com/harishassan-code/hospital-care/issues/58) | Done in code; the last check is the first staging build's `check --deploy` line | Record it in the B13 operations notes after the deploy |
| [#59](https://github.com/harishassan-code/hospital-care/issues/59), [#69](https://github.com/harishassan-code/hospital-care/issues/69) | Staging needs the Render and Vercel account owner to deploy | Deploy from the [deployment guide](../../setup/deployment.md), then run `scripts/smoke_staging.py` |
| [#60](https://github.com/harishassan-code/hospital-care/issues/60) | Report and slides are done; the Sprint 8–9 records are added after these ceremonies | Fill in this review and the retrospective on 27 Nov; Sprint 9 on 4 Dec |

## Backlog changes from PO feedback
- _at the review_

## Staging
URL demoed: _at the review_ (not deployed on 23 Nov) · Commit: `main` at `b5278f2` passed the staging rehearsal on
23 Nov (production settings, PostgreSQL, the full browser scenario)
