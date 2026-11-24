# What each staff page is for (B22)

Every staff page answers one question, shown under its title, leads with what needs action, and puts its trend charts
below the things to act on. Checked page by page at review. The questions live in
`frontend/src/features/staff/purposes.ts`; the charts in `frontend/src/features/charts/`.

| Page | The question it answers | What it leads with | Charts |
|---|---|---|---|
| Overview | What needs me now? | Status tiles and attention items, each linking to where it's fixed | Emergency arrivals and departures per hour today against a typical day; bed occupancy over 7 days |
| **Emergency department** (new) | Who is waiting, who is next, and why is the wait what it is? | Who is next, with *Start treatment*; the queue in triage order; being treated (discharge, admit, transfer); admitted patients waiting for a ward bed | Arrivals per hour against typical; estimated wait over 24 hours; waiting by triage level. *Why this wait* lists the factors |
| Emergency cases | Which cases still lack something, and since when? | The cases, newest first, with *New case* and *Request blood* | Cases opened per day by severity, 7 days |
| Beds | Where can the next patient go, and which beds free up soon? | Ward boards with each bed's actions | Occupancy by bed type over 7 days; beds freeing up in the next 12 hours (being cleaned, due home today) |
| Blood bank | Which groups run short, and what expires first? | The stock grid and units reserved for cases | Red cells by group against each group's minimum; issued and donated per day, 14 days |
| Donors | Who can donate now, and who is booked? | Search and the donor list | Donations per day, 14 days |
| Operating rooms | Which rooms are free now and later today, and is the list running late? | Rooms with their status actions | Today's lists per room with a line at the time now (booked, should be running, done, cancelled); theatre use over 7 days |
| **Staff on duty** (new) | Who is on duty now, who is missing, and is any department short? | Who isn't in, with *Clock in now* and *Mark absent* | Patients per nurse by department against the most it should have; doctors and nurses on duty through the day against the rota |
| Equipment | Which devices are free, and which are out of service? | The register with status actions | Ventilators in use over 24 hours |
| Ambulances | Which vehicles are free, and which trips are under way? | The fleet with status actions | Trips per hour against typical; trips per day, 7 days |
| Pharmacy | What runs out first? | Stock with search and filters | Days of stock left for the medicines nearest their reorder point |
| Transfers | What is on its way to us, and from us? | Incoming and outgoing with their actions | Transfers per day to us and from us, 14 days |
| City command centre | Which hospitals are under strain, and what is moving between them? | Hospitals ranked by strain (occupancy line over 24 hours, emergency wait, critical blood groups where the hospital keeps blood, escalated cases) | The ranking's sparklines; the figures table as before |
| Reports | What happened over a period? | The period and the CSV and PDF exports | Cases by severity; time to fulfil by severity |
| Simulation | How fast does the city run, and what is happening in it? | The clock's controls | — |
| Alerts, Audit log, Hospitals, Specialists, Users and roles | — | Their list or form | None: their purpose is a list or a form |

## Charts

`frontend/src/components/charts/`: `ChartFrame` (title, what it shows, legend, *Show as table*, when it was updated),
`TimeSeriesChart` (lines with an optional typical-day band and threshold line; hover, or focus and use the arrow keys,
for every series at that time), `BarChart` (plain or stacked, an optional threshold line per bar or for all), `Timeline`
and `Sparkline`. SVG and CSS with the design tokens only, in light and dark. The series colours (`--chart-1` to
`--chart-3`) passed the data-visualisation palette checker in both modes; status is always a word as well as a colour
("Low", "Short", "Reorder"). Every chart has the same figures as a table. Charts load after the page, so the page's
own content and actions never wait on them; they refresh every minute.

The figures come from `GET /api/metrics/` ([api.md](../architecture/api.md#trend-figures-b22)): each hospital's hourly
snapshots (B20, kept going by the simulation, B21).
