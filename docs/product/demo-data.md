# Demo data: the CityCare network on staging

**Bolt:** B20 · **Code:** `backend/apps/core/management/commands/seed_demo.py` and `backend/apps/core/seed/`
(`profiles.py` for the hospitals, `resources.py`, `staffing.py`, `history.py`)

Staging has no real data and never will. `seed_demo` builds a synthetic city network that behaves like a real
one, so the pages, charts and the simulation (B21) mean something. This page says what's in it and where each
proportion comes from: a published figure where one exists, otherwise our own assumption, marked as such.

## Rules

- **Everything is synthetic.** People's names are drawn from common Pakistani first names and surnames; donors are
  marked "(demo)". Patients carry initials or a tag, never a name. Hospital names are made up and checked against
  the hospitals listed for Karachi (a test fails if one matches a real hospital's name); addresses are areas, not
  buildings.
- **The scenario stays exact.** The demo script and the end-to-end test (B12) were written for the first three
  hospitals, and their stock is unchanged: CityCare General has exactly one usable O− red-cell unit and two free
  ventilators (VENT-003, VENT-005); Seaview and Northside have two O− red-cell units each, and Seaview's expire first
  in the network, so it ranks first as the source.
- **Repeatable.** The same `--seed` (default 7) gives the same data; each hospital and each part has its own random
  stream, so adding a hospital changes nobody else's data. A re-run adds only what's missing; `--reset` starts over.

## The network

| Hospital | Area | Kind | Beds | Emergency arrivals/day |
|---|---|---|---|---|
| CityCare General Hospital | Shahrah-e-Faisal | Teaching hospital, all services | 208 | 210 |
| Seaview Hospital | Clifton | Cardiac centre | 86 | 70 |
| Northside Children's Hospital | North Nazimabad | Children's hospital, NICU, burns | 76 | 95 |
| Eastgate Trauma Centre | Korangi | Trauma, orthopaedics, neurosurgery, burns | 160 | 240 |
| Lotus Women's Hospital | Gulshan-e-Iqbal | Women's and maternity, NICU | 110 | 45 |
| Harbourline District Hospital | Kemari | District general hospital | 130 | 150 |
| Orangi Hills Hospital | Orangi Town | Secondary care, no ICU | 96 | 130 |
| Malir Valley Hospital | Malir | General, renal unit | 116 | 120 |
| Bahadurabad Medical Centre | Bahadurabad | Private multi-specialty | 106 | 55 |
| Metro Blood Centre | Saddar | Regional blood bank | – | – |

Together: 1,088 beds, 31 ambulances, 37 operating rooms, about 360 pieces of critical equipment, about 1,700 blood
units, about 1,100 doctors and nurses on rosters, and 14 days of hourly history.

## Proportions and sources

| Item | Value used | Source |
|---|---|---|
| Blood groups among donors | B+ 33%, O+ 28%, A+ 22%, AB+ 7%, Rh-negative about 10% | Pakistani donor studies: Rawalpindi/Islamabad B 34%, O 31%, Rh+ 91% ([PAFMJ](https://www.pafmj.org/PAFMJ/article/view/1767)); Lahore B 34%, O 33%, Rh+ 91% ([PAFMJ](https://www.pafmj.org/PAFMJ/article/view/4694)); Karachi O+ 31.9%, B+ 31.2%, Rh+ 97% ([PJMD 2024](https://ojs.zu.edu.pk/pjmd/article/view/163)). Our shares follow the larger Punjab and Islamabad samples; Karachi's own data puts O+ slightly ahead |
| Component shares of stock | red cells 56%, plasma 24%, platelets 12%, cryoprecipitate 8% | Assumption (a typical component mix) |
| Shelf lives | red cells 42 days, platelets 5 days, plasma and cryo a year | Standard blood bank storage practice |
| Blood stock | about five days of red cells at each blood bank | Assumption |
| Bed occupancy | public hospitals 85–95%, intensive care 90–95%, private 65–80% | Assumption, in line with reports of overcrowded public hospitals |
| Intensive care beds | about 5–10% of a general hospital's beds | Assumption |
| Nurse to patient on a shift | intensive care 1:2, emergency 1:4, wards 1:8 | Between the recommended (about 1:4 on wards) and what is reported in Pakistani hospitals (1:8 to over 1:10): [Dunya News](https://dunyanews.tv/en/Pakistan/336408-Dim-one-to-eight-nursepatient-ratio-in-Pakistan-h), [Nursing in Pakistan](https://en.wikipedia.org/wiki/Nursing_in_Pakistan) |
| Shifts | nurses 08–14, 14–20, 20–08, six days in seven; doctors 08–20 and 20–08, five days in seven | Assumption (the hospital's shifts in `config/hospital.ts`) |
| Doctors | about one per 12 beds per shift, per department | Assumption |
| Clock-ins | within about 10 minutes of the start; about 6% late, about 3% missed | Assumption |
| Ventilators | about one per intensive care bed, mostly in use | Assumption |
| Operating lists | 08:00 to about 17:00, cases of one to three hours with half an hour between, about 80% of slots booked | Assumption |
| Emergency arrivals | lowest 03:00–05:00, highest 10:00–13:00 and 18:00–21:00; Mondays about 12% busier | Assumption (the usual daily shape of emergency attendance) |
| Emergency wait | about 15 minutes when quiet, rising steeply as arrivals pass what the department can see, at most four hours; people waiting = arrivals × wait (Little's law) | Model, see `history.py` (`er_wait_minutes`); the simulation (B21) uses the same |
| Beds through the day | fullest around 08:00, emptiest around 17:00 (after the day's discharges) | Assumption |

## History (for the charts)

Hourly figures for the last 14 days per hospital (`apps/metrics`, catalogue in `catalog.py`): beds occupied and in
service per bed type, emergency arrivals, departures, people waiting and wait, usable red cells, units issued and
donated, theatres in use, ventilators in use, doctors and nurses on duty, and ambulance trips. Each series ends at
the live figure, so a chart's last point matches the page. The simulation (B21) keeps adding to it.
