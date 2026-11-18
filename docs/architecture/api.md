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

Units need **blood: view** to read and **blood: edit** to change (admin, bloodBank). Donors and appointments need
**donors: view** / **donors: edit** (admin, bloodBank; see [api-contracts](api-contracts.md#access-stories-12)). Staff only see
and change their own hospital's units, donors and appointments (**403** otherwise). Every change is audit-logged.

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
  eligible: boolean, ineligibleReason: string, eligibleFrom: string | null,  // null + ineligible = permanent
  hospitalId: number | null  // read-only; null for a donor an admin registered with no hospital
}
Appointment = { id: number, donorId: string, donorName: string, startsAt: string, slotMinutes: number,
                status: 'booked' | 'cancelled', hospitalId: number | null }  // hospitalId read-only
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
- **Cross-hospital (B11):** booking, screening or cancelling a donor or appointment of another hospital → **403**
  (admins: any hospital). The booking goes to the actor's hospital, or the donor's if the actor has none.

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

## Transfers (#47, #48, #49)

Module `transfers`: admin, doctor, nurse and blood bank can use it; pharmacist and patient get 403. A transfer asks another
hospital for stock of one need of a case: blood or equipment only (beds and operating rooms are patient transfer,
#63 to #65). Shapes are in `frontend/src/api/transfers.ts`.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/transfers/?direction=incoming\|outgoing&status=` | – | 200 `Transfer[]`, newest first |
| POST | `/transfers/` | `{itemId, supplierId, quantity, note?}` | 201 `Transfer` |
| GET | `/transfers/<id>/` | – | 200 `Transfer` |
| POST | `/transfers/<id>/actions/` | `{action, reason?, note?}` | 200 `Transfer`, after the move |

```ts
Transfer = {
  id: number,
  case: { reference: string, severity: string },
  itemId: number,
  resourceType: 'blood' | 'equipment',
  need: string,                          // "A+ red cells", "Ventilator"
  supplier: { id: number, name: string },
  receiver: { id: number, name: string },  // the case's hospital
  quantity: number,
  approved: number,                      // holds made for it so far: "2 of 4 approved"
  resources: string[],                   // one per hold: "A+ red cells DN-0042"
  status: 'requested' | 'approved' | 'dispatched' | 'inTransit' | 'delivered' | 'rejected' | 'cancelled',
  reason: string,                        // why it was rejected or cancelled
  requestedBy: string,
  createdAt: string,
  history: { fromStatus, toStatus, action, note, actor: string | null, at: string }[],  // oldest first
  actions: ('approve' | 'reject' | 'dispatch' | 'startTransit' | 'deliver' | 'cancel')[]  // what this user may do now
}
```

- **Direction.** `incoming` is where your hospital is the supplier, `outgoing` where it is the receiver. Without it you get
  both. Admins see the whole network; a user with no hospital sees nothing. Bad `direction` or `status` is 400.
- **Asking (#47).** The case must be visible to you (its need is 404 otherwise), and you must edit emergencies at the
  case's hospital (admins: any). Otherwise 403. Refused with 400 and nothing saved:
  - `{"supplierId": [...]}` when the supplier is the case's own hospital, or not an active hospital.
  - `{"itemId": [...]}` for a bed or an operating room.
  - `{"quantity": ["Only 2 more can be asked for this need."]}` when the quantity is more than the need has left: its
    quantity, less its fulfilled units, its holds and the requests still waiting for an answer.
  - `{"detail": "Can't ask for stock for a case that is closed."}` for a fulfilled, closed or cancelled case.
  A new transfer is `requested`. Nothing is reserved yet.
- **Moves (#47, #48).** The lifecycle is the table in the [tracking spec](../aidlc/inception/2026-11-18-transfer-tracking.md):

  | From | Action | To | Who |
  |---|---|---|---|
  | requested | approve | approved | supplier |
  | requested | reject (reason required) | rejected | supplier |
  | requested | cancel | cancelled | requester |
  | approved | dispatch | dispatched | supplier |
  | approved | cancel | cancelled | requester |
  | dispatched | startTransit | inTransit | supplier |
  | dispatched | deliver | delivered | receiver |
  | dispatched | cancel | cancelled | requester |
  | inTransit | deliver | delivered | receiver |
  | inTransit | cancel | cancelled | requester |

  "Supplier" is edit on the resource's module (`blood` or `equipment`) at the supplying hospital. "Requester" for cancel is
  edit on `emergencies` at the receiving hospital. "Receiver" for deliver is edit on the module at the receiving hospital.
  Admins can make any move. `actions` lists exactly the moves the table allows from the current status and the user may make.
- **Approval** holds the units at the supplier through `reserve`, in one transaction. If fewer are free, what is free is
  held (partial approval). If none is free, or the case can no longer take stock, it is **409** and the transfer stays
  `requested`.
- **Refusals:** a move the lifecycle doesn't allow, or a receipt that a unit or the case refuses, is **409**
  `{"detail": "Can't deliver a transfer that is approved."}`; nothing changes. A move the user may not make is **403**
  `{"detail"}`. A transfer that involves neither of the user's hospitals is **404**. `reject` without a reason is
  **400** `{"reason": ["Say why the request is rejected."]}`. `cancel` takes an optional `reason`; the other moves take `note`.
  Every move can carry a `note`, which goes in the history.
- **Holds are pinned (#47).** The holds of a live transfer (approved, dispatched or in transit) are never swept by expiry.
  The case page can't release them (409 `{"detail": "This hold is part of transfer #7; cancel the transfer instead."}`) or
  allocate them (409, "receive the transfer instead"), and `canAllocate` is false. Each case reservation gains
  `transfer: {id, status} | null`, the live transfer it belongs to. Cancelling releases them, and each unit goes back on
  the supplier's shelf, even after dispatch.
- **Receipt (#49).** `deliver` (from dispatched or in transit) runs in one transaction. For each held unit: its hospital
  becomes the receiver, its storage place is cleared and its location says "Received from <supplier>" (cut to the field's
  length). Then `allocate` issues it (blood) or puts it in use (equipment), writes the allocation (its hospital stays the
  supplier), and the case is recomputed. Last, the transfer is `delivered`. Any refusal, such as a unit that expired on the
  way or a case that closed meanwhile, undoes every unit: nothing moves, nothing is allocated and the transfer stays where
  it was.
- **Audit:** `transfer.requested`, `transfer.approved`, `transfer.rejected`, `transfer.cancelled`, `transfer.dispatched`,
  `transfer.inTransit` and `transfer.delivered`, each with the status before and after. Per unit on receipt,
  `<model>.transferred` (`bloodunit` or `equipment`) with the hospital before and after, then `allocation.created`.
- **Case detail** gains `transfers`: the case's transfers, newest first, in the same shape, with the moves this user may make.
  Each reservation gains `transfer`, as above.
- **Admin:** read-only. Transfers are asked, answered and received in the app, so every move is checked and recorded.
- **Trips (#51).** While an ambulance carries a transfer, no manual move is offered and the move is **409**
  `{"detail": "An ambulance is carrying this transfer. Use the trip's steps instead."}`: `approve`, `reject`, `dispatch`,
  `startTransit`, `deliver` and `cancel` alike. A case that closes or is cancelled while its trip is on the road is **409**
  too, and nothing changes. The transfer gains `trip` (its latest [trip](#trips-51), or null), `etaMinutes` (the supplier to
  receiver estimate) and, when it is approved and the user may dispatch, the move `dispatchAmbulance` in `actions`.

## Ambulances (B04, #50)

The ambulance registry: each ambulance at its base hospital, with its type and status. Access: admin and nurse **edit**,
doctor **view**; other roles 403. Staff see their own hospital's ambulances; admins see all. Every registration and move is
audit-logged. Trips use the same ambulances: see [Trips](#trips-51).

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/ambulances/?type=&status=&q=&hospital=` | – | `Ambulance[]`, by type then asset tag (`q` searches the asset tag, `hospital` is a hospital id) |
| POST | `/ambulances/` | `{identifier, type, hospitalId?}` | 201 `Ambulance` |
| POST | `/ambulances/<id>/actions/` | `{action, reason?}` | 200 `Ambulance` |

```ts
Ambulance = {
  id: number, identifier: string,   // asset tag, stored upper-case, unique within a hospital (400 otherwise)
  type: 'basic' | 'advanced' | 'patientTransport',
  status: 'available' | 'dispatched' | 'maintenance' | 'outOfService',  // a new ambulance starts available; 'dispatched' is "On trip"
  statusSince: string,
  hospital: string | null,          // the base hospital's name
  trip: { id: number, status: 'dispatched' | 'enRoute' | 'arrived', transferId: number } | null  // the trip on the road, if any
}
```

- **Registering.** A non-admin registers at their own hospital; a `hospitalId` they send is ignored. An admin sends
  `hospitalId`, or uses their own hospital. With neither: 400 `{"hospitalId": [...]}`. A tag already used at that hospital
  (any case): 400 `{"identifier": [...]}`. A 400 saves nothing. `status` can't be set on registration.
- **Moves** (the lifecycle is in `apps/ambulances/models.py`): `startMaintenance` (available → maintenance),
  `finishMaintenance` (maintenance → available), `outOfService` (available or maintenance → out of service) and
  `returnToService` (out of service → maintenance). A move the status doesn't allow is **409** `{"detail": "Can't
  outOfService a vehicle that is out of service."}` and changes nothing. Unknown action → 400. `dispatch` and `release`
  are the trip's moves: this endpoint refuses them with **409** `{"detail": "A trip moves this vehicle. Use the transfer's
  trip instead."}`, and a vehicle on a trip can't be moved by hand (**409**, "Can't startMaintenance a vehicle that is on trip.").
- Another hospital's ambulance is **404** for a non-admin. A role without access gets **403**, signed out too.
- **Audit:** `ambulance.registered` (identifier, type, status) and `ambulance.status_changed` (status before and after,
  with the optional `reason`).

## Dashboard refresh (#54, B08)

No new endpoint. The staff workspace reloads the data its pages share every 30 seconds, with the same GET calls as its first
load for the user's role: beds, blood units, pharmacy stock, `GET /emergencies/`, `GET /transfers/?direction=incoming` and
`?direction=outgoing` (the transfers module only), and the public ER status. The reload is skipped while the tab is hidden
and while another reload is running, and runs once when the tab is shown again. A reload that fails keeps the data on
screen. The next one tries again.

Each reload runs the escalation sweep of `GET /emergencies/` again, as the first load does. That is fine at MVP scale.

## City command centre (#55)

Module `commandCentre`: admin only, view. Every other role, and a signed-out caller, gets **403**. The page lives at
`/staff/command-centre`. Shapes are in `frontend/src/api/commandCentre.ts`.

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/command-centre/` | – | 200 `CommandCentre` |

```ts
CommandCentre = {
  updatedAt: string,                     // when the figures were taken; the page shows it
  nearExpiryDays: number,                // the window "near expiry" means, from BLOOD_NEAR_EXPIRY_DAYS (3)
  totals: Figures,                       // sums of the hospital rows; redCells carry no level
  hospitals: (Figures & { id: number, name: string })[]   // active hospitals only
}
Figures = {
  redCells: { group, available, minimum, level: 'ok' | 'low' | 'critical' }[],  // 8 groups; totals: { group, available }
  components: { redCells | plasma | platelets | cryo: { usable, nearExpiry } },
  beds: { icu, emergency, general, isolation, nicu },        // free beds
  equipment: { ventilator, monitor, defibrillator, dialysis }, // available
  operatingRooms: number,                                     // available
  cases: { active, escalated },
  open: { blood, bed, equipment, operatingRoom }              // quantity − fulfilled − held, over active cases
}
```

- **Who is counted.** Active hospitals only (`is_active`), as matching counts them. Usable stock is `available` and not past
  expiry, so reserved, quarantined, issued and expired units don't count. Free beds are `free`; equipment and rooms are
  `available`, so held or busy ones don't. Active cases are `open`, `matching`, `partiallyFulfilled` and `escalated`.
- **Levels.** Red cells only, judged per hospital against the minimum in `RED_CELL_MINIMUM` (a copy of `MINIMUM_STOCK.redCells`
  in `blood.ts`; a test keeps them equal). `critical` below half the minimum, `low` below it, otherwise `ok`. The totals never
  carry a level.
- **Order.** Hospitals with a critical red-cell group come first, then the rest by name.
- **Sweeps first.** The read runs `escalate_overdue()` and `release_expired()`, as the feed and the case pages do, so held
  stock and escalated cases match those pages.
- **Read only.** A write is refused (403), even for an admin.
- **Contents.** Counts, hospital names and ids. No patient field, case reference, unit or asset identifier, and no staff name.
- **Cost.** A fixed number of queries whatever the number of hospitals: seven grouped reads for the figures, plus the two
  sweeps (10 in all on the seeded network, budget 15). A test adds two hospitals and checks the count doesn't change.
- **Refresh.** The server holds nothing; the page reads again every 60 seconds while the tab is visible. Each read runs
  the sweeps, which is why the period is a minute.

## Audit trail (#56)

Admins search the audit trail and export it to CSV. Both endpoints are read only: POST, PUT, PATCH and DELETE answer
**405**. Anyone else, and a signed-out user, gets **403** (`audit: view`, admins only; superusers act as admins). The rules
are in `apps/audit/services.py`.

| Method | Path | Returns | Access |
|---|---|---|---|
| GET | `/api/audit/entries/` | `{count, limit, offset, results}` | audit: view |
| GET | `/api/audit/entries/export/` | CSV attachment, `audit-<date>.csv` | audit: view |

- **Filters** are optional and combine with AND. `actor` is the account's email, exact and ignoring case; it still matches
  after the account is deleted. `action` is a starts-with match (`bed.` finds every bed action). `targetType` and `targetId`
  are exact (use both for one object's history). `from` and `to` are `YYYY-MM-DD`, each a whole day in `Asia/Karachi`, and
  both ends are included. `q` is a case-insensitive contains match over `actorEmail`, `action`, `targetRepr`, `targetId` and
  `reason`, not over `before` or `after`.
- **400** `{"detail": "..."}` for a date that doesn't parse, a `to` before `from`, or a `limit` or `offset` that isn't a whole
  number (negative values included).
- **Paging** on the search: `limit` defaults to 50 and is cut to 200; `offset` defaults to 0. Results are newest first (`at`
  descending, then `id` descending).
- **Result rows:** `{id, at, actorEmail, action, targetType, targetId, targetRepr, reason, before, after}`. `at` is ISO 8601 in
  UTC. `before` and `after` are the recorded JSON values, or `null`.
- **Export:** the same filters, in the same column order as the rows above, with `at` in UTC. `before` and `after` are JSON
  text in one cell each, empty when there is no value. A cell starting with `=`, `+`, `-`, `@`, a tab or a carriage return
  gets a leading `'`. The file holds at most **10,000** rows: over that, the answer is **400** `{"detail": "..."}` and no file.
  Rows are read in chunks, not loaded all at once.
- **Audit:** each completed export writes `audit.exported` (target: the exporting admin's account; `after` holds the filters
  and the row count). An export that is refused, or never read to the end, writes nothing. Searches and page views aren't
  logged.
- **Queries:** a page costs two queries (one count, one select), however many rows it holds.

## Notifications (#52)

Staff are told about events at their hospital (see the [notification spec](../aidlc/inception/2026-11-18-notification-service.md)).
Each row belongs to one person. Anyone signed in as staff (`IsStaff`) may read their own rows: patients and signed-out
users get **403**. Admins without a hospital get an empty list. Shapes are in `frontend/src/api/notifications.ts`.

| Method | Path | Success |
|---|---|---|
| GET | `/notifications/?unread=true` | 200 `Notification[]`, the user's 50 newest, newest first. `unread` is optional: `true` or `1` keeps only unread, `false` or `0` (or none) returns all. Any other value is 400. |
| GET | `/notifications/unread-count/` | 200 `{count}` |
| POST | `/notifications/<id>/read/` | 200 `Notification`, with `readAt` set |

```ts
Notification = {
  id: number,
  kind: string,                 // "case.created", "case.escalated", "reservation.created", "reservation.released",
                                // "reservation.expired", "transfer.requested", "transfer.approved", "transfer.rejected",
                                // "transfer.dispatched", "transfer.cancelled", "transfer.delivered"
  severity: 'critical' | 'info',
  message: string,              // up to 300 characters
  link: string,                 // "/staff/emergencies/EC-2026-0001", "/staff/transfers", or "" when there is none
  createdAt: string,
  readAt: string | null         // null until read
}
```

- **Who is told.** `notify` (in `apps/notifications/services.py`) is called next to the audit record of each event. It
  writes one row for each active user whose hospital is the one named and whose role can edit the module named. The
  actor who made the move is left out. A user with no hospital gets nothing.
  - **Case side** (`emergencies` at the case's hospital): a critical case created (`critical`), a case escalated by hand or
    automatically (`critical`), holds made, released or expired at the case's own hospital (`info`, one row per move, not
    per unit), and the transfer answers approved, rejected and dispatched (`info`).
  - **Supplier side** (the resource's module at the supplying hospital): a transfer requested (`critical`), and cancelled or
    delivered (`info`). Blood goes to the blood bank and admins; equipment to nurses and admins.
  - Starting transit notifies nobody. A hold at another hospital (a transfer's, at the supplier) notifies nobody.
- **Rollback.** `notify` runs inside the move's transaction, so a move that rolls back keeps no notification.
- **Read.** `readAt` is set once. A second call returns the row with the first time. Another person's row, or an unknown
  id, is **404**.
- **Audit.** Rows are not audit-logged: each copies an event that already is. Marking one read the first time writes
  `notification.read` (target: the notification). A repeat call changes nothing and writes nothing.
- **Web UI (B07, #53).** The bell, the critical banners and the Alerts page poll the list (all, and `?unread=true`) and the count
  every 30 seconds while the tab is visible, and once when it is shown again. A 401 or 403 stops polling. There is no read-all
  endpoint: each alert is marked read on its own.
- **Admin.** Read-only. Rows are written by `notify` and only `read_at` is set by the API.

## Trips (B05, #51)

An approved transfer is carried by one available ambulance from its supplying hospital. The trip records the ETA, who sent
it and when, and steps through the road: dispatched → en route → arrived → completed. The trip is simulated: buttons, no
GPS. Access: edit on `ambulances` at the **supplying** hospital (admin: any hospital) for dispatch and every step. The
receiving hospital sees the trip on the transfer, read only. Outsiders get 404. Spec:
[B05](../aidlc/bolts/B05-ambulance-dispatch.md) and [its inception spec](../aidlc/inception/2026-11-18-ambulance-dispatch.md).

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/transfers/<id>/trips/` | `{ambulance}` | 201 `Trip` |
| POST | `/trips/<id>/actions/` | `{action: "depart" \| "arrive" \| "complete", note?}` | 200 `Trip`, after the step |

```ts
Trip = {
  id: number, transferId: number,
  status: 'dispatched' | 'enRoute' | 'arrived' | 'completed',
  ambulance: { id: number, identifier: string, type: string },
  etaMinutes: number,               // set once, at dispatch: the supplier-to-receiver estimate, rounded to whole minutes
  dispatchedBy: string,             // the person's name, or their email
  dispatchedAt: string, departedAt: string | null, arrivedAt: string | null, completedAt: string | null,
  actions: ('depart' | 'arrive' | 'complete')[]   // the steps this user may take now
}
```

- **Dispatch (201).** The transfer must be **approved** (**409**, "Can't dispatch a transfer that is requested."). The
  ambulance must be **available** (**409**, "Can't dispatch a vehicle that is on trip."). It must be based at the transfer's
  supplier (**400** `{"ambulance": [...]}`). A transfer has at most one active trip and an ambulance has at most one: a second
  is **409**, and the database enforces both (partial unique constraints). A transfer or ambulance the user can't see is
  **404**. A user who may not edit ambulances at the supplier is **403** (the receiving hospital included). A missing
  ambulance is 400. Refusals change nothing.
- **Steps.** `depart`: dispatched → en route, and the transfer moves to **in transit** through the transfer service.
  `arrive`: en route → arrived; the transfer stays in transit. `complete`: arrived → completed; the ambulance goes back to
  **available**, and the transfer **stays in transit**: receipt is the receiver's confirmation (B03), never a side effect of
  a trip. Any other step is **409** `{"detail": "Can't arrive a trip that is dispatched."}` and changes nothing. A completed
  trip is final.
- **Locks.** Every write is one `transaction.atomic()` that locks the case, the need, the transfer, then the trip and the
  ambulance (the order transfers use). A failure after either move undoes both.
- **Audit:** `trip.dispatched`, `trip.departed`, `trip.arrived`, `trip.completed`, each with the status before and after,
  plus the moves the trip makes: `ambulance.status_changed` (dispatch and release), `transfer.dispatched` and
  `transfer.inTransit`.
- **Lists.** `GET /ambulances/` shows each ambulance's `trip`. Dispatch offers only available ambulances at the supplier
  (`?status=available&hospital=<supplier id>`).

## Demo data

```bash
docker compose exec backend python manage.py seed_demo          # safe to re-run
docker compose exec backend python manage.py seed_demo --reset  # start the demo data over
```

Creates 3 hospitals (CityCare General, Seaview, Northside Children's) with 10 departments, 12 wards / 164 beds
(ICU, emergency, general, isolation and NICU) and 10 storage locations, plus 320 blood units (with screening results), 60 synthetic donors (two deferred) and 6 upcoming donation
appointments, 23 medicines, 14 doctor shifts, seven ambulances (two per hospital and a patient transport at CityCare General), three operating rooms per hospital with a few bookings today and
tomorrow, the ER status, and one login per
role (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`, `patient@demo.citycare.pk`, password
`CityCare-demo-1`). Demo only: never run it against real data.
