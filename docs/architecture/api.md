# Backend API (Sprint 1)

Sprint 2 endpoints (users, hospitals, structure) are in [api-contracts.md](api-contracts.md).

Base URL: `http://localhost:8000/api` locally. All bodies are JSON. Field names match the TypeScript types in
`frontend/src/api/`, so each frontend `get…()` function can switch from sample data to the real call unchanged.

## Auth (session cookie + CSRF)

The browser keeps a Django session cookie. Every request must use `credentials: 'include'` (the shared client
already does). Signed-in `POST`s must send the `X-CSRFToken` header from the `csrftoken` cookie (the client
already does); the cookie is set by `login`, `signup`, `me` and `csrf`.

| Method | Path | Who | Body | Success | Errors |
|---|---|---|---|---|---|
| GET | `/auth/csrf/` | anyone | – | 200, sets `csrftoken` cookie | – |
| POST | `/auth/login/` | anyone | `{email, password}` | 200 `User` | 400 bad input (email > 254 or password > 512 characters), 401 wrong email/password (same message for both), 429 after 5 failed attempts on the account (locked 15 min) |
| POST | `/auth/logout/` | anyone | – | 204 | 403 if CSRF header missing |
| POST | `/auth/signup/` | anyone | `{full_name, email, phone?, password}` | 201 `User` (always a patient) | 400 `{email: [...]}` taken, 400 `{password: [...]}` weak |
| GET | `/auth/me/` | signed in | – | 200 `User` | 403 when signed out |

`User` = `{id, email, fullName, phone, role, isStaff}`; `role` is one of `admin`, `doctor`, `nurse`,
`bloodBank`, `pharmacist`, `patient` (same ids as `features/staff/roles.ts`). Staff accounts are created in
Django admin, never through sign-up.

## Modules

Access follows `ACCESS` in `features/staff/roles.ts` (enforced in `apps/accounts/permissions.py`):
reading needs *view*, changing needs *edit*. No access → 403.

| Method | Path | Returns | Access |
|---|---|---|---|
| GET | `/public/status/` | `PublicStatus` (ER status + today's doctors) | anyone, no sign-in |
| GET | `/beds/` | `BedBoard` = `{wards, beds}` | beds: view |
| POST | `/beds/<bed id>/actions/` | `{action}` → updated `Bed` | beds: edit |
| GET | `/blood/units/` | `BloodUnit[]` | blood: view |
| GET | `/pharmacy/stock/` | `Medicine[]` with `batches` | pharmacy: view |

Bed actions: `discharge`, `markReady`, `reserve`, `cancelReservation`, `outOfService`, `returnToService`.
A move the bed lifecycle doesn't allow (e.g. reserving an occupied bed) returns **409** and changes nothing.
Unknown action → 400, unknown bed → 404. Discharging clears the patient details.

A blood unit past its expiry date is reported as `expired` (unless already `issued`), even if nobody has
updated its stored status yet.

## Blood bank (Sprint 3)

Every endpoint needs **blood: view** to read and **blood: edit** to change (admin, bloodBank). Staff only see and
change their own hospital's units, donors and appointments (**403** otherwise). Every change is audit-logged.

| Method | Path | Body | Success | Story |
|---|---|---|---|---|
| GET | `/blood/units/?status=&group=&component=` | – | `BloodUnit[]`; `status=available` never returns expired units | #18 |
| POST | `/blood/units/` | `{id, group, component, collectedAt, expiresAt?, location, donorId?}` | 201 `BloodUnit` | #17, #20 |
| GET | `/blood/units/<id>/` | – | `BloodUnitDetail` | #18 |
| POST | `/blood/units/<id>/tests/` | `{test, passed, reason?}` | 201 `BloodUnitDetail` | #18 |
| POST | `/blood/units/<id>/actions/` | `{action, reason?}` | 200 `BloodUnitDetail` | #18 |
| GET | `/blood/stock/?nearExpiryDays=3` | – | `BloodStock` | #19 |
| GET | `/blood/donors/?q=&bloodGroup=` | – | `Donor[]` (search by name, code or phone) | #20 |
| POST | `/blood/donors/` | `{fullName, bloodGroup, phone?, email?}` | 201 `Donor` (code `DNR-00001`, …) | #20 |
| GET | `/blood/donors/<id>/` | – | `Donor` + `units: BloodUnit[]` | #20 |
| POST | `/blood/donors/<id>/screening/` | `{eligible, reason?, deferredUntil?}` | 200 `Donor` | #21 |
| GET | `/blood/appointments/` (`?all=true` for past and cancelled) | – | `Appointment[]`, upcoming booked | #22 |
| POST | `/blood/appointments/` | `{donorId, startsAt}` | 201 `Appointment` | #22 |
| POST | `/blood/appointments/<id>/cancel/` | – | 200 `Appointment` | #22 |

```ts
BloodUnitDetail = BloodUnit & {
  donorId: string | null,
  tests: { test: Test, passed: boolean, reason: string, recordedAt: string }[],
  missingTests: Test[]          // tests still needed before release
}
Test = 'hiv' | 'hbv' | 'hcv' | 'syphilis' | 'malaria'
BloodStock = {
  nearExpiryDays: number, lowStockUnits: number,
  rows: { group, component, available, reserved, quarantined, nearExpiry: number, low: boolean }[],  // 8 groups × 4 components
  nearExpiryUnits: BloodUnit[]  // available units expiring within nearExpiryDays, soonest first
}
Donor = {
  id: string, fullName: string, bloodGroup: string, phone: string, email: string,
  lastDonationAt: string | null,
  eligible: boolean, ineligibleReason: string, eligibleFrom: string | null  // null + ineligible = permanent
}
Appointment = { id: number, donorId: string, donorName: string, startsAt: string, slotMinutes: number,
                status: 'booked' | 'cancelled' }
```

**Rules**

- **Screening (#18):** new units are `quarantined`. Each test is recorded once (repeat → 400). When all five have
  passed, the unit moves to `available` by itself. A failed test needs a `reason` and moves the unit to
  `discarded`. Tests on a unit that isn't quarantined → 409.
- **Unit actions:** `reserve`, `cancelReservation`, `issue`, `expire`, `release` (409 unless every test passed),
  `discard` (400 without a reason). A move the lifecycle doesn't allow → 409.
- **Expiry (#19):** units past their expiry date are marked `expired` (audit-logged, actor "system") by
  `python manage.py expire_blood_units` (schedule it hourly) and every time the stock view loads.
- **Stock (#19):** only `available` units count. `low` is true below `BLOOD_LOW_STOCK_UNITS` (default 5).
  `nearExpiryDays` defaults to `BLOOD_NEAR_EXPIRY_DAYS` (3); 0–60, otherwise 400.
- **Donors (#20):** synthetic identities only. A unit's group must match its donor's group (400 on `donorId`).
- **Eligibility (#21):** a donor can't give again within `BLOOD_MIN_DONATION_INTERVAL_DAYS` (56). Units collected
  the same day count as one donation (components). Screening `{eligible: false}` needs a reason; no
  `deferredUntil` means a permanent deferral. `{eligible: true}` clears it.
- **Appointments (#22):** on a `BLOOD_APPOINTMENT_SLOT_MINUTES` (30) boundary, in the future. One booked donor
  per hospital per slot (the database enforces it, so two people booking at once can't both win → 400).
  Ineligible donors and donors who already have an upcoming appointment → 400. A cancelled slot can be rebooked.

All four `BLOOD_*` settings can be changed with environment variables of the same name.

## Emergency cases (#30, #32)

Module `emergencies`: admin, doctor and nurse can open cases and move them; blood bank and pharmacist can view them.
Users at a hospital see only its cases (another hospital's case → **404**); staff with no hospital see every case.

| Method | Path | Body | Success | Story |
|---|---|---|---|---|
| GET | `/emergencies/` | – | `EmergencyCase[]`, most severe first, then oldest first. Escalates overdue cases first (#35) | #30, #31, #35 |
| POST | `/emergencies/` | `{severity, patientRef?, items}` | 201 `EmergencyCase` | #30, #31, #32 |
| GET | `/emergencies/<id>/` | – | `EmergencyCaseDetail`: the case with its `history`, `actions`, `outcome`, local availability and its holds (`reservations`). Escalates overdue cases and frees expired holds first (#35, #43) | #30, #33, #34, #35, #43 |
| POST | `/emergencies/<id>/actions/` | `{action, note?}` | 200 `EmergencyCaseDetail`, after the move (see [Status](#status-and-its-timeline-34)) | #34 |
| GET | `/emergencies/feed/?type=blood\|bed\|equipment\|operatingRoom` | – | `FeedEntry[]`: every hospital's active requests of that type, most urgent first, at most 100. Escalates overdue cases first (#35) | #36, #38 |
| GET | `/emergencies/<id>/candidates/` | – | `CandidatesResponse`: the other hospitals that can supply each short need, and the hospitals judged across all of them (see [Sources in the network](#sources-in-the-network-38) and [Hospitals across the needs](#hospitals-across-the-needs-42)). Does not escalate; frees expired holds first (#43) | #38, #42, #43 |
| POST | `/emergencies/<id>/reservations/` | `{itemId, quantity}` | 201 `CaseReservation[]`: the holds made at the case's own hospital (see [Stock holds](#stock-holds-43)) | #43 |
| POST | `/emergencies/<id>/reservations/<holdId>/release/` | – | 200 `CaseReservation`, now `released`; 409 when it is no longer held | #43 |

```ts
EmergencyCase = {
  id: string,                   // "EC-2026-0001": sequential per year
  severity: 'critical' | 'high' | 'moderate' | 'low',  // most severe first
  status: 'open' | 'matching' | 'partiallyFulfilled' | 'fulfilled' | 'escalated' | 'closed' | 'cancelled',
  patientRef: string,           // optional bed/triage tag, ≤ 30 chars; never a name
  hospital: { id: number, name: string } | null,
  createdBy: string, createdAt: string,
  items: RequestItem[]          // 1–10
}
RequestItem = { type: 'blood', group: BloodGroup, component: Component, quantity: number }  // 1–20
            | { type: 'bed', bedType: 'icu' | 'emergency' | 'general' | 'isolation' | 'nicu', quantity: number }  // 1–5
            | { type: 'equipment', equipmentType: 'ventilator' | 'monitor' | 'defibrillator' | 'dialysis', quantity: number }  // 1–5
            | { type: 'operatingRoom', capability: 'general' | 'cardiac' | 'trauma' | 'neuro' | 'orthopedic' | 'obstetric' | 'pediatric', quantity: number }  // 1–3
```

- **Equipment and operating rooms (#32, completed in #38).** A need sends only the field of its type: `equipmentType` for
  equipment, `capability` for an operating room. Missing that field is **400**. Fields of other types are ignored and stored
  blank. The line limits are lower for rooms (3) than for equipment (5), as beds are (5).

**Rules**

- A new case is always `open`, at the creator's hospital, and audit-logged (`emergencyrequest.created`). Its first
  timeline entry is the creation. Later moves are in [Status and its timeline](#status-and-its-timeline-34).
- **Severity (#31):** `critical`, `high`, `moderate`, `low`. The list is sorted by severity, then by age with the oldest
  case first within a level (the case waiting longest is handled first). The server does the sort; clients render
  the order they receive. Ties (same severity and time) fall back to id. Cases from before #31 were renamed:
  `urgent` → `high`, `routine` → `moderate`.
- A blood request is a case with one blood need. Send it through `POST /emergencies/` with `severity` as its urgency
  and `items: [{type: 'blood', group, component, quantity}]`. It gets the same validation, reference, timeline,
  audit record and escalation as any case. See [Network request feed](#network-request-feed-36).
- No patient-identifying data is collected: `patientRef` is optional.
- Errors on one need come back keyed by its position: `{"items": {"0": {"quantity": ["..."]}}}`. An empty or
  over-long list is `{"items": ["..."]}`.

### Status and its timeline (#34)

```ts
EmergencyCaseDetail = EmergencyCase & {
  history: StatusChange[],      // oldest first; the first entry is the creation
  actions: CaseAction[]         // the moves valid from the current status, in table order
}
StatusChange = {
  fromStatus: CaseStatus | '',  // '' for the creation entry
  toStatus: CaseStatus,
  action: CaseAction | 'create',
  note: string,                 // up to 500 characters, may be ''
  actor: string | null,         // the user's name, or email if they have no name; null for the system (an automatic
                                //   escalation, #35) and for a user who has since been removed; the UI shows "System"
  at: string                    // ISO time
}
CaseAction = 'startMatching' | 'partiallyFulfil' | 'fulfil' | 'escalate' | 'resumeMatching' | 'close' | 'cancel'
```

`POST /emergencies/<id>/actions/` takes `{"action": "startMatching", "note": "Blood bank called back"}`. `note` is
optional, except for `close` (see [Escalation and closure](#escalation-and-closure-35)). Responses:

| Status | When |
|---|---|
| 200 | The move is made. The body is the case as it now is: its new `history` entry and its `actions`. |
| 400 | `action` is not a move in the lifecycle, or `note` is over 500 characters. Closing with a blank note is `{"note": ["Add an outcome note to close the case."]}`. Nothing changes. |
| 403 | The role can view emergencies but not change them (blood bank, pharmacist), or the user is not staff. |
| 404 | No such case, or another hospital's case (admins: any hospital). Nothing changes. |
| 409 | The lifecycle does not allow the move from the current status: `{"detail": "Can't close a case that is open."}`. Nothing changes and no timeline entry is written. |

**Transitions** (`REQUEST_LIFECYCLE` in `backend/apps/emergencies/models.py`):

| From | Action | To |
|---|---|---|
| open | startMatching | matching |
| matching | partiallyFulfil | partiallyFulfilled |
| matching | fulfil | fulfilled |
| partiallyFulfilled | fulfil | fulfilled |
| open, matching, partiallyFulfilled | escalate | escalated |
| escalated | resumeMatching | matching |
| fulfilled, partiallyFulfilled, escalated | close | closed |
| open, matching | cancel | cancelled |

`closed` and `cancelled` are terminal: no move leaves them. Until allocation sets fulfilment (#45), staff make every
move by hand.

Each move writes one timeline entry and one audit record (`emergencyrequest.status_changed`, with the before and after
status). The audit reason is the note, or the action when there is no note; the audit log keeps 300 characters of it.
The status change, the entry and the audit record are written in one transaction.

Reads follow the hospital rule above. So an admin who works at one hospital can move another hospital's case, as the
rule for moves says, but cannot open its page. That is an open question in the
[#34 inception spec](../aidlc/inception/2026-11-17-emergency-status-tracking.md).

### Local availability (#33)

The detail says what the case's own hospital has for each need. The list does not carry these fields.

```ts
EmergencyCaseDetail = EmergencyCase & {
  items: (RequestItem & {
    itemId: number,             // the need's id, for reserving stock for it (#43)
    localAvailable: number,     // usable stock at the case's hospital that matches this need exactly, free of holds
    shortfall: number,          // max(0, quantity - fulfilled - held - allocated - localAvailable)
    reserved: number            // the need's holds not yet allocated (#43)
  })[],
  shortfallTotal: number,       // sum of the items' shortfall: units and beds still needed from other hospitals
  reservations: CaseReservation[]  // the holds on the case's stock, held and allocated (#43)
}
```

- **Blood** counts units at the case's hospital that are **exact** matches: the same group and the same component,
  status `available`, and not expired (`expires_at` after now, the same rule as the stock view). Quarantined, reserved,
  issued, discarded and expired units do not count. **Compatible groups do not count** (O− for an A+ need, for example):
  cross-group matching is story #37.
- A resource held by a reservation (#43) is in its reserved status, so it no longer counts in any of the above.
- **Beds** count free beds (`status` `free`) of the need's `bedType` at the case's hospital.
- **Equipment** counts available equipment (`status` `available`) of the need's `equipmentType` at the case's hospital.
  In use, in maintenance and out of service do not count.
- **Operating rooms** count available rooms (`status` `available`) at the case's hospital whose capabilities include the
  need's `capability`. A room is one unit of stock: a room with two capabilities covers one line, so a cardiac line and a
  general line that both want it leave one of them short. Lines take rooms in list order, the lowest id first.
- Requirements that draw on the same stock share it in list order: the first sees the whole stock, the next sees what
  is left after it.
- A case with no hospital has `localAvailable` 0 for every need, so each need's shortfall is what is still unfulfilled.
- A need's holds (#43) come off its quantity before its shortfall is worked out, so a case does not ask other hospitals
  for stock it already holds here. A held resource is not free, so it is not in `localAvailable` either.
- The shortfalls are computed on read and never stored. The matching step (#38) reads them through
  `shortfall_items(case)` in `backend/apps/emergencies/availability.py`.

### Escalation and closure (#35)

**Escalation.** A **critical** case in status `open`, `matching` or `partiallyFulfilled` is escalated to `escalated` when
its latest timeline entry (the time it entered that status) is older than `EMERGENCY_ESCALATION_MINUTES` minutes
(default 30, a whole number of 1 or more; the server does not start on any other value). Other severities, and cases
that are escalated, fulfilled, closed or cancelled, are never escalated automatically. A case resumed to `matching`
after an escalation gets a fresh window, because its resume is a new entry.

- The move is the same one a person makes (`escalate`), written through the same code: one timeline entry and one audit
  record (`emergencyrequest.status_changed`), both with **no actor**. The note is
  `Not fulfilled within 30 minutes (automatic)`, with the setting's value. The timeline shows the actor as **System**.
- It runs as a request-time sweep: the case list and the case detail check and escalate overdue cases before they
  answer, so staff see an up-to-date state. The check is one query when nothing is overdue. The sweep covers every
  hospital's cases, whoever is reading.
- A management command runs the same check and prints the count, for a scheduler later:
  `python manage.py escalate_overdue_cases` → `Escalated 2 overdue cases.`. Running it twice escalates nothing the
  second time.
- Two runs at once do not escalate the same case twice: each candidate is locked with `skip_locked`, and its status and
  latest entry are checked again under the lock.

**Closing needs an outcome note.** `POST /emergencies/<id>/actions/` with `{"action": "close"}` needs a `note` that is not
blank (spaces only count as blank). Without one the answer is **400** `{"note": ["Add an outcome note to close the case."]}`
and nothing changes. A close the lifecycle refuses (a case that is already closed, say) is still 409, checked first.
Other moves keep their note optional.

The outcome note is the note of the close entry in the timeline. The detail shows it as `outcome`:

```ts
EmergencyCaseDetail = EmergencyCase & {
  outcome: string | null        // the note of the close entry; null until the case is closed
}
```

## Network request feed (#36)

`GET /emergencies/feed/` lists the network's active requests so that a blood bank at another hospital can see what is
wanted. Module `emergencies`: every role that can see emergencies can read it (admin, doctor, nurse, blood bank,
pharmacist). Patients and signed-out users get **403**. It is not limited to the user's own hospital; that is the point.

Query: `type` is `blood` (default), `bed`, `equipment` or `operatingRoom`. Any other value is **400**
`{"type": ["..."]}`.

```ts
FeedEntry = {
  reference: string,            // "EC-2026-0001"
  hospital: { id: number, name: string } | null,
  severity: 'critical' | 'high' | 'moderate' | 'low',
  status: 'open' | 'matching' | 'partiallyFulfilled' | 'escalated',
  createdAt: string,            // ISO time; the client shows its age
  needs: FeedNeed[]             // only the needs of the requested type
}
FeedNeed = { type: 'blood', group, component, quantity: number, fulfilled: number }
         | { type: 'bed', bedType, quantity: number, fulfilled: number }
         | { type: 'equipment', equipmentType, quantity: number, fulfilled: number }
         | { type: 'operatingRoom', capability, quantity: number, fulfilled: number }
```

- **Included:** cases in status `open`, `matching`, `partiallyFulfilled` or `escalated`, from every hospital (and cases
  with no hospital), that have at least one need of the requested type. Each entry lists only those needs.
- **Excluded:** `fulfilled`, `closed` and `cancelled` cases, and cases with no need of the requested type.
- **Order:** severity (critical first), then the oldest case first, then id. The same order as the case list.
- **Limit:** the first 100 entries. There is no paging yet (a ponytail in `views.py`).
- **Escalation:** the feed runs the same request-time sweep as the list and the detail (#35), so an overdue critical
  case appears here already `escalated`.
- **Not included, on purpose:** `patientRef`, notes, the timeline, `outcome`, and who created the case (`createdBy`).
  The feed crosses hospitals, so it carries no patient-related data and nothing about staff at another hospital.
  The case's own page (`GET /emergencies/<id>/`) is still limited to its hospital, so a link to another hospital's case
  is a 404. The client links only the user's own hospital's entries.
- **Queries:** a fixed number, whatever the number of cases: the sweep's check, the cases with their hospitals, and
  their needs.

## Sources in the network (#38)

`GET /emergencies/<id>/candidates/` lists, for each need the case's own hospital cannot cover, the other hospitals that
can supply it. Module `emergencies`, read rule as for the case detail: every role that can see emergencies, limited to
the case's hospital, so another hospital's case is **404** and a patient is **403**.

```ts
CandidatesResponse = {
  reference: string,               // "EC-2026-0001"
  items: CandidateItem[],          // only the short needs; [] when everything is covered locally
  hospitals: HospitalMatch[]       // the hospitals across all the short needs at once (#42); [] when nothing is short
}
CandidateItem = {
  itemId: number,                  // the RequestItem's id
  need: string,                    // label: "O- red cells", "ICU bed", "Ventilator", "Cardiac operating room"
  shortfall: number,               // what the case's hospital cannot cover (#33)
  strategy: { name: string, label: string },  // how the candidates are ordered (#40), e.g. {"name": "earliestExpiry", "label": "Earliest expiry first"}
  candidates: Candidate[]          // best first: rank 1 is the recommendation (#41)
}
Candidate = {
  hospital: { id: number, name: string },
  available: number,               // matchable at that hospital for this need
  covers: boolean,                 // available >= shortfall
  distanceKm: number | null,       // straight-line, one decimal
  travelMinutes: number | null,    // estimated travel time (#39), whole minutes
  earliestExpiry?: string,         // blood only: the soonest expiry among its matching units
  bestDonorRank?: number,          // blood only: 0 is the identical group, higher is a compatible substitute
  rank: number,                    // 1-based position in the item's list (#41)
  score: Score,                    // the breakdown of the ranking (#41)
  recommended: boolean             // true only on rank 1, and only when its score is above 0
}
Score = {
  total: number,                   // 0 to 100, one decimal: the sum of the factors' points
  strategy: string,                // the strategy's name, as in CandidateItem.strategy.name
  factors: ScoreFactor[]           // in the strategy's order
}
ScoreFactor = {
  name: 'distance' | 'expiry' | 'quantity' | 'compatibility',
  label: string,                   // "Distance", "Expiry", "Stock", "Blood group match"
  value: number,                   // 0 to 1, two decimals: how well the candidate does on this factor
  weight: number,                  // this factor's share of the strategy's weights, 0 to 1, two decimals
  points: number,                  // one decimal, out of 100: the factor's contribution to the total
  detail: string                   // the reason in plain words: "4.2 km, about 6 min", "expires in 3 days", "5 available, 3 needed", "identical group"
}
```

- **Matchable**, per requirement type (the registry in `backend/apps/matching/candidates.py`): blood units that #37
  allows for the recipient group and component and that are usable; beds free of the type; equipment available of the
  type; operating rooms available with the capability. Each is counted per hospital.
- **Left out:** the case's own hospital (its stock is already counted in #33), inactive hospitals, and hospitals with
  nothing matchable.
- **Order (#41):** by total score, highest first, from the strategy for the need's type (#40: earliest expiry for blood,
  nearest for beds, equipment and operating rooms, weights from `MATCHING_SCORING`). Ties go to the nearer candidate (no
  distance last), then to hospital id. Covering is not a sort key: stock depth counts only through the Stock factor, so
  a candidate that covers less can rank above one that covers more when its distance and expiry are much better. The
  client shows this order as received.
- **Scores (#41).** Each factor's points are rounded to one decimal before they are added, so the points shown add up
  exactly to `total`. `recommended` is set on rank 1 only, and not when its total is 0 (for example, when only distance
  counts and the hospital is beyond `MATCHING_MAX_DISTANCE_KM`). The case page shows `distanceKm` and `travelMinutes` with
  each candidate as "4.2 km · ~6 min", or "distance unknown" when `distanceKm` is null.
- **Distance** is `null` when the case has no hospital or either side has no coordinates.
- **Per requirement.** Two needs can both count the same unit at another hospital. Allocation (#45) is what claims stock.
- **Read only.** Nothing is stored, and the endpoint does not run the overdue sweep (#35).
- **Queries:** a fixed number: the case with its needs and local stock (as in #33), one grouped query per short need, and
  one hospital fetch for all the candidates together. It does not query per hospital.

## Hospitals across the needs (#42)

`hospitals` in `GET /emergencies/<id>/candidates/` judges each hospital that is a candidate for at least one short need
across all of those needs at once: which needs it covers in full, and what it is missing for the rest. Same access
rule as the sources above. It adds no query: it is worked out from the candidates already fetched.

```ts
HospitalMatch = {
  rank: number,                    // 1-based position in the list
  hospital: { id: number, name: string },
  complete: boolean,               // covers every short need
  recommended: boolean,            // true only on rank 1, and only when complete
  coverage: string,                // "2 of 3": the needs covered, of the short needs
  coveredCount: number,
  totalNeeds: number,              // the number of short needs
  score: number,                   // the mean of its #41 candidate scores over the needs it has candidates for, one decimal
  distanceKm: number | null,       // as on a candidate (#39)
  travelMinutes: number | null,
  covered: { itemId: number, need: string }[],
  unmet: { itemId: number, need: string, missing: number, available: number }[]
    // every need not covered in full: partial ones (available > 0) and ones it has none of (available 0)
}
```

- **Order:** complete first; then the most needs covered; then the score, highest first; then the nearer hospital (no
  distance last); then hospital id. Ties are stable.
- **Shared stock.** Needs that draw on the same stock at one hospital (two O− red-cell lines, two ICU bed lines, two
  lines for the same operating-room capability) share its count. Each is judged in item order: the first line is covered
  first, and the next sees what is left. So one hospital is not credited twice with the same units. `available` in
  `unmet` is what is left for that line.
- **Known limit: blood across groups.** The candidates for blood are grouped per need, so two needs with different
  groups (for example O− and A+ red cells) can both count the same donor unit at a hospital. Allocation (#45) resolves
  this exactly.
- **Known limit: operating rooms with two capabilities.** A room that serves two capabilities counts for each of them.
  Two needs of different capabilities can then both count it. Allocation (#45) resolves this too.
- **The score only breaks ties** between hospitals that cover the same number of needs. A complete hospital ranks above
  any partial one, whatever its score.
- **Empty** (`[]`) when nothing is short. A hospital with none of the needs does not appear.

## Equipment (Sprint 4)

Critical equipment that can be located and shared (#26). Access: admin and nurse **edit**, doctor **view**; other
roles 403. Staff see only their own hospital's equipment; every registration is audit-logged.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/equipment/?type=&status=&q=` | – | `Equipment[]` (`q` searches asset tag, make/model and location) |
| POST | `/equipment/` | `{identifier, type, name?, location, status?}` | 201 `Equipment` |
| POST | `/equipment/<id>/actions/` | `{action, reason?}` | 200 `Equipment` (#27) |

```ts
Equipment = {
  id: number, identifier: string,   // asset tag, stored upper-case, unique within a hospital (400 otherwise)
  type: 'ventilator' | 'monitor' | 'defibrillator' | 'dialysis',
  name: string, location: string,
  status: 'available' | 'reserved' | 'inUse' | 'maintenance' | 'outOfService',  // defaults to available
  statusSince: string, hospital: string | null
}
```

Equipment actions (#27): `use`, `release`, `reserve`, `cancelReservation`, `startMaintenance`, `finishMaintenance`,
`outOfService`, `returnToService`. `reserve` and `cancelReservation` are the moves a hold makes (#43); see [Stock holds](#stock-holds-43). The lifecycle is in `apps/equipment/models.py`. A move it doesn't allow (e.g. using equipment
that is in maintenance) returns **409** and changes nothing. Unknown action → 400; equipment outside the user's
hospital → 404. Every change is audit-logged (`equipment.status_changed`) with the optional `reason`.
`Equipment.objects.matchable()` returns only `available` items; the matching engine uses it so in-use,
maintenance and out-of-service equipment is never matched.

## Operating rooms (Sprint 4)

Operating rooms and what each is equipped for (#28). Access: admin and nurse **edit**, doctor **view**; other
roles 403. Staff see only their own hospital's rooms; every registration is audit-logged. Bookings (#29) below.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/operating-rooms/?capability=&status=&q=` | – | `OperatingRoom[]` (`q` searches name and location; an unknown `capability` or `status` is ignored) |
| POST | `/operating-rooms/` | `{name, capabilities, location?, status?}` | 201 `OperatingRoom` |
| POST | `/operating-rooms/<id>/actions/` | `{action, reason?}` | 200 `OperatingRoom` (#28) |

```ts
OperatingRoom = {
  id: number, name: string,   // e.g. "OR 1"; unique within a hospital, any case (400 otherwise)
  capabilities: ('general' | 'cardiac' | 'trauma' | 'neuro' | 'orthopedic' | 'obstetric' | 'pediatric')[],
                              // at least one (400 otherwise); stored sorted, without repeats
  location: string,           // e.g. "Block B, floor 2", may be empty
  status: 'available' | 'reserved' | 'inUse' | 'cleaning' | 'maintenance' | 'outOfService',  // defaults to available
  statusSince: string, hospital: string | null
}
```

Actions: `startCase`, `reserve`, `cancelReservation`, `finishCase`, `finishCleaning`, `startMaintenance`,
`finishMaintenance`, `outOfService`, `returnToService`. `reserve` and `cancelReservation` are the moves a hold makes
(#43); `startCase` from `reserved` starts a case that held the room. The lifecycle is in `apps/operating_rooms/models.py`. A move it doesn't allow returns **409**
and changes nothing. Unknown action → 400. A room outside the user's hospital → 404 (admins can change any
hospital's room). Registration is audit-logged as `operatingroom.registered`; status changes as
`operatingroom.status_changed` (the shared `change_status` helper names them after the model).
`OperatingRoom.objects.matchable()` returns only `available` rooms, and `with_capability(code)` filters by capability.

### Bookings and the day schedule (story #29)

Booking a slot is open to admin, nurse and doctor (`orBookings`: edit); the day view needs `operatingRooms` view.
Other roles get 403. Same own-hospital rule: another hospital's room is **404**.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/operating-rooms/schedule/?date=YYYY-MM-DD` | – | `Schedule` (`date` defaults to today, local time; a bad date → 400) |
| POST | `/operating-rooms/bookings/` | `{roomId, startsAt, endsAt, procedure, surgeon?, patientInitials?}` | 201 `Booking` |
| POST | `/operating-rooms/bookings/<id>/cancel/` | – | 200 `Booking`, now `cancelled`; 409 if it already is; 403 for someone else's booking unless admin or nurse |

```ts
Schedule = { date: string, rooms: { id, name, status, capabilities, bookings: Booking[] }[] }
   // every room in the user's hospital (every room for a user without one), by name
Booking = {
  id: number, roomId: number,
  startsAt: string, endsAt: string,   // ISO 8601 with offset, e.g. "2030-01-15T09:00:00+05:00"
  procedure: string, surgeon: string, patientInitials: string,  // surgeon and initials may be ""
  status: 'booked' | 'cancelled', bookedBy: string                // bookedBy is the booker's full name
  canCancel: boolean   // admins and nurses can cancel any booking, others (surgeons) only their own
}
```

- **Half-open times.** A booking covers `[startsAt, endsAt)`: 10:00–11:00 and 11:00–12:00 in the same room are
  both allowed. A booking must end after it starts, last at most 24 hours, and start in the future (5 minutes of
  slack). An out-of-service room is refused (400).
- **Overlaps are refused twice.** The service locks the room row and answers **400**
  `{"startsAt": ["OR 1 is already booked from 10:00 to 11:00."]}` (times in local time). The database
  backstops it with an exclusion constraint on `operating_rooms_orbooking` (PostgreSQL only; SQLite can't
  express it, so the migration skips it there):

  ```sql
  EXCLUDE USING GIST (
    (int8range(room_id, room_id, '[]')) WITH &&,
    (tstzrange(starts_at, ends_at, '[)')) WITH &&
  ) WHERE (status = 'booked')
  ```

  Two range expressions stand in for `btree_gist`'s room `=`, so the extension isn't needed. Cancelled rows are
  outside the condition, so a cancelled slot can be booked again. A `CHECK (ends_at > starts_at)` covers every
  backend.
- Booking and cancelling are audit-logged as `orbooking.created` and `orbooking.cancelled`. Cancelling keeps the row.
- The schedule lists only `booked` slots that overlap the local calendar day, in time order. A slot that runs past
  midnight appears on both days.

## Stock holds (#43)

A case can hold local stock while staff decide. A hold moves the resource to its reserved status (`reserve`), so every
search for stock stops offering it: the local availability, the candidates for other cases, the compatible blood units
and the matchable equipment and rooms. Nothing new filters them; they look for an available or free status.

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/emergencies/<id>/reservations/` | `{itemId, quantity}` | 201 `CaseReservation[]`, the holds made |
| POST | `/emergencies/<id>/reservations/<holdId>/release/` | – | 200 `CaseReservation`, now `released` |

Module `emergencies`, **edit**. The case is looked up under the user's hospital (another hospital's case is **404**), and
a role without edit rights is **403**.

```ts
CaseReservation = {
  id: number,
  itemId: number,                          // the need it is for
  resource: string,                        // "O- red cells DN-0042", "Bed ICU-03", "Ventilator VENT-003" or "OR 1"
  hospital: { id: number, name: string },  // the resource's hospital
  status: 'held' | 'allocated' | 'released' | 'expired',
  expiresAt: string,                       // when an unused hold runs out
  reservedBy: string                       // the person's name, or their email
}
```

- **Reserving** takes stock at the case's own hospital: up to `quantity` of the need's resources. Blood comes in donor
  rank order, then earliest expiry, then id (the compatibility order of #37, so exact groups first); the other types by
  id. If fewer are free, what is there is taken and the response lists the holds, so the caller sees the count.
- **Refused** with **400** and nothing changed:
  - `{"detail": "No matching stock is free at this hospital."}` when nothing is free.
  - `{"detail": "Only 2 more can be reserved for this need."}` when `quantity` is more than the need has left: its
    quantity, less its fulfilled count and its active holds.
  - `{"detail": "Can't reserve stock for a case that is closed."}` for a fulfilled, closed or cancelled case.
  - `{"itemId": ["No need with that id on this case."]}` for a need that is not on this case, and `{"quantity": [...]}`
    for a quantity below 1.
- **Release** answers **409** `{"detail": "This reservation is released, so it can't be released."}` when the hold is not
  `held` any more (allocated, released or expired). A released hold returns its resource to its available or free status.
  If the resource has already moved on (issued, expired), the hold ends and the resource is left as it is.
- **Hold time:** `RESERVATION_HOLD_MINUTES` (default 30), set on the hold when it is made. Changing the setting later does
  not move the holds already made. See [deployment](../setup/deployment.md#resource-holds-43).
- **Expiry** releases every held hold past its `expiresAt` back to stock, and records it as `expired` with no actor. It
  runs before the candidates GET, the case detail GET and both reservation endpoints, and from the management command
  `python manage.py release_expired_reservations`, which prints how many it released.
- **Case move:** reserving stock for an **open** case moves it to **matching**, as a system move (its timeline entry has
  no actor). An escalated, matching or partially fulfilled case stays where it is.
- **Audit:** `reservation.created` for each hold (the resource, its expiry and the reason), `reservation.released`,
  `reservation.expired`, and `<model>.status_changed` for each resource move.
- **Detail:** `reservations` lists the held and allocated holds of the case. Each item's `reserved` counts its held ones.

## Allocations (#45, #46)

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/reservations/?status=held&type=blood` | – | 200 `HeldReservation[]`: held holds at your hospital (every hospital for admins) |
| POST | `/reservations/<id>/allocate/` | `{note?}` (≤ 500) | 201 `Allocation` |
| POST | `/reservations/allocate/` | `{ids: number[]}` (1–50) | 201 `Allocation[]`, all or nothing |

```ts
HeldReservation = {
  id, type: 'blood' | 'bed' | 'equipment' | 'operatingRoom',
  case: {reference, severity, status},
  need: {itemId, label, quantity, fulfilled, remaining},
  resource: string,             // e.g. "O- red cells DN-0042"
  expiresAt, reservedBy,
  canAllocate: boolean          // whether you may allocate this one
}
Allocation = {id, itemId, resource, hospital: {id, name}, allocatedBy, at, note}
```

- **One transaction.** Allocating locks the case, the need, the hold and the resource (the same order as reserving),
  then does all of these or none:
  - moves the resource to its final state: blood `issue`d, bed `admit`ted (no patient recorded), equipment `use`d,
    room `startCase`
  - marks the hold `allocated`
  - adds 1 to the need's `fulfilled`
  - writes a permanent `Allocation`
  - moves the case as a system move: to `partiallyFulfilled` after the first allocation, to `fulfilled` once every
    need is complete. An `open` case goes through `matching`, and an `escalated` one through `resumeMatching`.
- **Who may allocate:** edit on the resource's module (blood for blood, beds, equipment, operatingRooms) at the
  resource's hospital. Admins may allocate network-wide. Anyone else gets 403. These views declare `IsAuthenticated`,
  and the per-type check runs on each hold.
- **Refused (409, nothing saved):** a hold that isn't `held` or has passed its `expiresAt`, or a case that is
  `fulfilled`, `closed` or `cancelled`. An unknown id is 404.
- **The list** is ordered most urgent case first (severity, then the oldest case), then the hold expiring first.
  It only shows the types your role can see. Asking for a type you can't see is 403.
- **Permanent:** there is no endpoint to change or delete an allocation, and the admin page is read-only.
- **Case detail:** gains `allocations` (oldest first), and each item gains `fulfilled` and `remaining`
  (`quantity − fulfilled`). Each reservation entry gains `canAllocate`. The page merges allocations into the
  timeline in time order.
- **Audit:** `allocation.created`, plus `<model>.status_changed` for the resource move.
- Expired holds are released before each of these endpoints answers, as for reservations.

## Demo data

```bash
docker compose exec backend python manage.py seed_demo          # safe to re-run
docker compose exec backend python manage.py seed_demo --reset  # start the demo data over
```

Creates 3 hospitals (CityCare General, Seaview, Northside Children's) with 10 departments, 12 wards / 164 beds
(ICU, emergency, general, isolation and NICU) and 10 storage locations, plus 320 blood units (with screening results), 60 synthetic donors (two deferred) and 6 upcoming donation
appointments, 23 medicines, 14 doctor shifts, three operating rooms per hospital with a few bookings today and
tomorrow, the ER status, and one login per
role (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`, `patient@demo.citycare.pk`, password
`CityCare-demo-1`). Demo only: never run it against real data.
