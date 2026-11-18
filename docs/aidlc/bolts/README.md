# Bolt board

> **Generated** by `scripts/aidlc_board.py` from each bolt's front matter. Don't edit this table: change the
> bolt file and run `python3 scripts/aidlc_board.py`. CI fails if the two disagree.

A **bolt** is one short, time-boxed AIDLC cycle (1–3 days) owned by one person: Inception spec → approval →
Construction → PR → Operations notes. How to run one: [docs/aidlc/README.md](../README.md#4-bolts).

**To take a bolt:** set `owner:` to your GitHub handle and `status: In Progress` in its file, run the script,
and assign yourself the linked issue(s) on the board. Max 2 bolts in progress per person (working agreement).
A bolt can start once everything in **Depends on** is Done (or the bolt says which part can go ahead).

## Sprint 7 (15 pts)

| Bolt | Title | Issues | Pts | Priority | Depends on | Owner | Status |
|---|---|---|---|---|---|---|---|
| [B00](B00-scrum-records-catch-up.md) | Scrum records catch-up before the preliminary review | [#2](https://github.com/harishassan-code/hospital-care/issues/2) | 2 | highest | – | _unassigned_ | 🟢 Ready |
| [B01](B01-transfer-request.md) | Inter-hospital transfer request | [#47](https://github.com/harishassan-code/hospital-care/issues/47) | 5 | highest | – | codewithalphadotcom | ✅ Done |
| [B02](B02-transfer-tracking.md) | Transfer tracking | [#48](https://github.com/harishassan-code/hospital-care/issues/48) | 5 | high | B01 | codewithalphadotcom | ✅ Done |
| [B03](B03-delivery-confirmation.md) | Delivery confirmation | [#49](https://github.com/harishassan-code/hospital-care/issues/49) | 3 | high | B02 | codewithalphadotcom | ✅ Done |

## Sprint 8 (32 pts)

| Bolt | Title | Issues | Pts | Priority | Depends on | Owner | Status |
|---|---|---|---|---|---|---|---|
| [B04](B04-ambulance-registry.md) | Ambulance registry | [#50](https://github.com/harishassan-code/hospital-care/issues/50) | 3 | medium | – | codewithalphadotcom | 🔵 In Review |
| [B05](B05-ambulance-dispatch.md) | Ambulance dispatch and trip tracking | [#51](https://github.com/harishassan-code/hospital-care/issues/51) | 5 | medium | B02, B04 | codewithalphadotcom | 🔵 In Review |
| [B06](B06-notification-service.md) | Notification service | [#52](https://github.com/harishassan-code/hospital-care/issues/52) | 5 | high | – | codewithalphadotcom | 🔵 In Review |
| [B07](B07-alerts-ui.md) | In-app alerts UI | [#53](https://github.com/harishassan-code/hospital-care/issues/53) | 3 | medium | B06 | codewithalphadotcom | 🔵 In Review |
| [B08](B08-hospital-dashboard.md) | Hospital dashboard: requests, transfers and live refresh | [#54](https://github.com/harishassan-code/hospital-care/issues/54) | 3 | high | B01 | codewithalphadotcom | 🔵 In Review |
| [B09](B09-city-command-centre.md) | City command centre dashboard | [#55](https://github.com/harishassan-code/hospital-care/issues/55) | 5 | high | – | codewithalphadotcom | 🔵 In Review |
| [B10](B10-audit-search-export.md) | Audit search and export | [#56](https://github.com/harishassan-code/hospital-care/issues/56) | 3 | medium | – | codewithalphadotcom | 🔵 In Review |
| [B11](B11-donors-page.md) | Donors page for the existing donor API | [#20](https://github.com/harishassan-code/hospital-care/issues/20), [#21](https://github.com/harishassan-code/hospital-care/issues/21), [#22](https://github.com/harishassan-code/hospital-care/issues/22) | 5 | medium | – | codewithalphadotcom | 🔵 In Review |

## Sprint 9 (14 pts)

| Bolt | Title | Issues | Pts | Priority | Depends on | Owner | Status |
|---|---|---|---|---|---|---|---|
| [B12](B12-e2e-mvp-scenario.md) | End-to-end MVP scenario test | [#57](https://github.com/harishassan-code/hospital-care/issues/57) | 5 | highest | B03 | _unassigned_ | ⚪ Backlog |
| [B13](B13-security-performance.md) | Security and performance hardening | [#58](https://github.com/harishassan-code/hospital-care/issues/58) | 3 | high | – | _unassigned_ | 🟢 Ready |
| [B14](B14-staging-and-demo.md) | Staging deployment, demo data and demo script | [#59](https://github.com/harishassan-code/hospital-care/issues/59), [#69](https://github.com/harishassan-code/hospital-care/issues/69) | 3 | highest | – | _unassigned_ | 🟢 Ready |
| [B15](B15-final-report.md) | Final report and demo presentation | [#60](https://github.com/harishassan-code/hospital-care/issues/60) | 3 | highest | B00 | _unassigned_ | ⚪ Backlog |

## Stretch (15 pts)

| Bolt | Title | Issues | Pts | Priority | Depends on | Owner | Status |
|---|---|---|---|---|---|---|---|
| [B16](B16-specialists.md) | Specialist profiles and on-call availability | [#61](https://github.com/harishassan-code/hospital-care/issues/61), [#62](https://github.com/harishassan-code/hospital-care/issues/62) | 5 | low | – | _unassigned_ | 🟢 Ready |
| [B17](B17-patient-transfer.md) | Patient transfer: need check, destination and arrival | [#63](https://github.com/harishassan-code/hospital-care/issues/63), [#64](https://github.com/harishassan-code/hospital-care/issues/64), [#65](https://github.com/harishassan-code/hospital-care/issues/65) | 5 | low | B01 | _unassigned_ | ⚪ Backlog |
| [B18](B18-reports.md) | Operational reports and export | [#66](https://github.com/harishassan-code/hospital-care/issues/66), [#67](https://github.com/harishassan-code/hospital-care/issues/67) | 5 | low | B10 | _unassigned_ | ⚪ Backlog |

## Progress

⚪ Backlog: 4 · 🟢 Ready: 4 · 🟡 In Progress: 0 · 🔵 In Review: 8 · ✅ Done: 3
