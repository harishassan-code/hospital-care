# Inception Spec: Patient transfer: need check, destination and arrival

**Date:** 2026-11-18
**Author:** Krrishna, drafted with Claude for review
**Bolt:** [B17](../bolts/B17-patient-transfer.md)
**Related backlog item:** #63 need check, #64 destination selection, #65 transfer completion (Epic E6, stretch; builds on #33 [local availability](2026-11-17-local-availability-check.md), #38 [find candidate hospitals](2026-11-17-find-candidate-hospitals.md), #42 [multi-resource matching](2026-11-17-multi-resource-matching.md) and #47 [transfer request](2026-11-18-transfer-request.md))

## Problem

A critical case that its own hospital can't cover is already visible: the shortfall for each need (#33), the hospitals that can supply each need (#38) and, since #42, the best single destination. What is missing is the move itself. Nothing records that the patient is going to another hospital, the destination has no way to know the patient is coming, and when the patient arrives the case stays with the sending hospital. Its list, its stock holds and its history all still say the sending hospital owns it.

Roles:

- **Doctor or nurse at the case's hospital (sending):** sees the flag, picks the destination, requests the move, and can cancel it before arrival.
- **Doctor or nurse at the destination (receiving):** sees the incoming patient and confirms arrival. Admins can act for any hospital.
- **Blood bank and pharmacist** can read cases but not move them. Patients have no access.

The ambulance and the trip are not in this bolt. B05 covers ambulance dispatch.

## User stories

- As a doctor or nurse at a hospital that can't cover a critical case locally, I want the case flagged and the hospitals that can cover it listed, so that I see at once that the patient may need to move. (#63)
- As a doctor or nurse at that hospital, I want to request the move to the recommended destination, or to another hospital from the list, so that the move is on record and the destination knows the patient is coming. (#64)
- As a doctor or nurse at the receiving hospital, I want to confirm that the patient has arrived, so that the case moves to my hospital and appears in my list, with its history kept. (#65)

## Acceptance criteria

Refined from the bolt's three checkboxes. Each keeps the bolt's wording at its head.

**Need check (#63): flag raised when local availability check fails for critical requirements**

- [x] The case detail carries `transferFlag`: true when the case is `critical` and at least one need is short after local availability (holds count as local, #33 and #43). It is computed on read and never stored, like the shortfall.
- [x] The case page shows a "Transfer may be needed" notice naming the short needs. The notice goes when local stock covers them.
- [x] Cases of other severities don't raise the flag (see open question 2).

**Destination (#64): uses multi-resource matching to recommend a destination**

- [x] The destination list is `match_hospitals` (#42). The rank-1 hospital that has everything is marked Recommended. When no hospital has everything, the best partial one is still listed, with what it is missing.
- [x] With one short need the #42 panel isn't shown (it appears from two short needs), so the recommendation is the per-need rank 1, as today.
- [x] Staff at the case's hospital (edit on emergencies) can request a transfer to a hospital from that list, with an optional note. The request is refused (400, nothing saved) when the case has no hospital, nothing is short, the case can't take stock (the #43 statuses), the destination is the case's own or inactive, or the destination isn't in the list. A second open request for the same case is 409.
- [x] The request stores a snapshot of the destination's match at that moment: covered needs, missing needs, distance and travel time. It reserves nothing at the destination.

**Arrival (#65): arrival confirmation updates case ownership**

- [x] Confirming arrival sets `EmergencyRequest.hospital` to the destination in one transaction, and marks the transfer arrived with who and when.
- [x] Only staff at the destination with edit on emergencies, or an admin, can confirm. The sending hospital gets 403. A hospital in neither role gets 404.
- [x] Arrival releases the case's unallocated holds at the sending hospital, so the units go back on its shelf. Allocated ones stay. The case's requested (unanswered) stock transfers are cancelled. Approved, dispatched or in-transit ones refuse arrival with 409, naming them.
- [x] A transfer that is no longer requested (already arrived or cancelled) can't be confirmed: 409, nothing changes.
- [x] After arrival the case is in the destination's list and gone from the sending hospital's. Its timeline shows "Arrived at X from Y". The sending hospital still sees the transfer in its outgoing list.
- [x] Before arrival the destination sees the incoming patient on its Emergencies page: reference, severity, need labels, sending hospital and request time. It does not see the case detail, its stock, its holds or the patient reference.

**Cancel, close and audit**

- [x] The sending hospital can cancel a requested transfer, with a reason. Closing or cancelling the case cancels its requested transfer in the same transaction.
- [x] Every change writes an audit record: `patienttransfer.requested`, `patienttransfer.arrived`, `patienttransfer.cancelled`, `emergencyrequest.hospital_changed`.

## Design

### What exists and what's new

| Piece | Exists | New in B17 |
|---|---|---|
| Shortfall per need, holds counted | `local_availability` (#33, #43) and the case page's "Available here / Short" | `transferFlag` on the case detail |
| Ranked sources and best destination | `candidates_for_case`, `match_hospitals` (#38, #42), the `BestDestination` panel | Destination action and the request snapshot |
| Stock moving between hospitals | `apps.transfers`: moves, `cancel_for_case`, `receive` (B01 to B03) | Not reused for the patient. Its cancel rules are reused for the case's stock |
| Case ownership | `EmergencyRequest.hospital`, set once at creation | Changed on arrival |
| History | `RequestStatusChange` timeline; allocations merged into it on the page | Patient transfer rows merged in too |
| Audit | `apps.audit.services.record`; append-only `AuditLog` (read in Django admin until #56) | Four new audit actions |

### Model: `PatientTransfer` (migration `emergencies/0006`)

One row per request to move a case. It is also the ownership history. A case changes hospital only through an arrived row, so a second table would repeat it.

| Field | Notes |
|---|---|
| `request` (FK EmergencyRequest) | The case |
| `from_hospital`, `to_hospital` (FK Hospital, PROTECT) | Sending (the case's hospital when requested) and destination |
| `status` | `requested`, `arrived` or `cancelled` |
| `match` (JSON) | Snapshot of the destination's `HospitalMatch` at request time |
| `note`, `reason` | Why it was requested; why it was cancelled |
| `requested_by`, `requested_at`, `arrived_by`, `arrived_at` | Who and when. The arrival fields stay null until arrival |

Constraints: `from_hospital` differs from `to_hospital`, and a partial unique constraint on `request` where the status is `requested` allows one open transfer per case, as `Reservation` does for holds. There is no status-history table: at most one move follows the request, and the audit record carries it. `EmergencyRequest` gets no new field.

### State machine

`PATIENT_TRANSFER_LIFECYCLE`, a `StateMachine` in `apps/emergencies/models.py`: `requested` to `arrived` on `arrive`, and `requested` to `cancelled` on `cancel`. Arrived and cancelled are final. The case lifecycle does not change.

### Services (`apps/emergencies/patient_transfers.py`, new)

The rules live in services, per AGENTS.md. Each write is `transaction.atomic()` and locks in the order the other modules use: case, transfer, holds, then stock transfers and resources.

| Function | Does | Locks | Audit |
|---|---|---|---|
| `transfer_flag(case)` | Read only: critical, and a need is short (`shortfall_items`) | none | none |
| `request_patient_transfer(case, *, destination, note, actor)` | Checks the request rules, runs `candidates_for_case` and `match_hospitals` for the snapshot, creates the row | case | `patienttransfer.requested` |
| `arrive_patient(transfer, *, actor)` | Destination permission and lifecycle. Refuses if the case has approved, dispatched or in-transit stock transfers. Cancels requested stock transfers. Releases unallocated holds. Sets `hospital` and the status | case, transfer, holds, stock transfers | `patienttransfer.arrived`, `emergencyrequest.hospital_changed`, `reservation.released` per hold, `transfer.cancelled` per stock transfer |
| `cancel_patient_transfer(transfer, *, actor, reason)` | Sending permission and lifecycle | transfer | `patienttransfer.cancelled` |
| `cancel_open_patient_transfer(case, *, actor, reason)` | Called by `apply_case_action` on close or cancel, in the same transaction | case | `patienttransfer.cancelled` |

Notes:

- Cancelling stock transfers inside `arrive_patient` skips the per-move permission check, as `cancel_for_case` does. The case move has already checked the actor. It cancels only requested transfers, so it is a narrower variant of `cancel_for_case`.
- `arrive_patient` calls into `apps.transfers` with a late import, as `apply_case_action` already does, because transfers builds on emergencies.
- Refusals are `PatientTransferRefused` (400, with an optional field) and `PatientTransferConflict` (409), defined in `emergencies`.

### Endpoints

| Method | Path | Body | Success |
|---|---|---|---|
| POST | `/api/emergencies/<reference>/patient-transfer/` | `{destinationId, note?}` | 201 `PatientTransfer` |
| GET | `/api/patient-transfers/?direction=incoming` or `outgoing`, `&status=` | none | 200 `PatientTransfer[]`, newest first |
| POST | `/api/patient-transfers/<id>/actions/` | `{action: "arrive" or "cancel", reason?}` | 200 `PatientTransfer`, after the move |

The list sits at the API root. The case route `emergencies/<str:reference>/` would otherwise catch it. The case detail gains `transferFlag` and `patientTransfers`.

```ts
PatientTransfer = {
  id: number, reference: string, severity: Severity,
  status: 'requested' | 'arrived' | 'cancelled',
  from: { id: number, name: string }, to: { id: number, name: string },
  needs: string[],                  // need labels, as the sources list shows them
  match: HospitalMatchSnapshot,     // the #42 entry at request time
  requestedBy: string, requestedAt: string,
  arrivedBy: string | null, arrivedAt: string | null,
  note: string, reason: string,
  actions: ('arrive' | 'cancel')[]  // what this user may do now
}
```

The shape never carries `patientRef`, stock or holds.

### Permissions

`ACCESS` in `backend/apps/accounts/permissions.py` and `roles.ts` do not change. There is no new module and no nav item. The new routes use `emergencies`, and the services check the object rule, as `transfers` narrows its moves per action.

| Action | Role (module `emergencies`) | Object rule | Refused |
|---|---|---|---|
| Read the list | view (any role that sees emergencies) | Your hospital is the destination (incoming) or the sending hospital (outgoing). Admins see all | The list only shows yours |
| Request a transfer | edit | The case's hospital (`may_change`). Admins: any | 403 |
| Cancel | edit | The sending hospital. Admins: any | 403 at the destination, 404 at neither |
| Confirm arrival | edit | The destination. Admins: any | 403 at the sending hospital, 404 at neither |
| Read the case after arrival | view | Own-hospital rule, unchanged | 404 at the sending hospital |

### Frontend

- **Case page:** a "Transfer may be needed" notice when `transferFlag` is set. A **Transfer patient** button on the recommended destination row and on each candidate row (edit on emergencies only). A patient transfer panel with the open request and **Cancel transfer**. The timeline gains the transfer entries.
- **Emergencies list:** an **Incoming patients** panel, shown to staff with edit, with **Confirm arrival**. Outgoing requests sit beside it.
- **Code:** `api/emergencies.ts` gains the types and three calls. `test/mockApi.ts` mocks them. New components in `features/emergencies/`: `PatientTransferPanel.tsx` and `IncomingPatients.tsx`. `roles.ts` and `planned.ts` don't change.
- **Docs:** a "Patient transfers" section in `docs/architecture/api.md`.

### Concurrency and edge cases

- **Double confirm, or confirm after cancel:** both take the case lock, then the transfer lock. The second sees a non-requested status: 409, nothing changes.
- **Two requests for one case at once:** the partial unique constraint refuses the second: 409.
- **The destination's stock changes after the request:** the snapshot records why it was chosen. Arrival does not re-check destination stock, because the patient is already on the way. After arrival the shortfall is worked out at the destination, and its sources panel offers other hospitals if the case is still short.
- **The destination is deactivated after the request:** arrival still goes through, since refusing would leave the patient in transit. No new request can pick it.
- **The case is closed or cancelled while requested:** its transfer is cancelled in the same transaction, so no arrival can follow.
- **Until arrival the case is still the sender's:** holds, allocations and expiry work as now. Arrival releases whatever holds remain. Any that expired first are already gone.
- **The case becomes fulfilled while requested:** the open request stays valid. A new one can't be made, because a fulfilled case can't take stock.
- **Transfer again after arrival:** allowed, as a new request from the new hospital. The history keeps both rows.
- **Case with no hospital** (admin-created): refused with 400.

### Non-goals

- Ambulance dispatch, trip status (en route, arrived) and ETAs. B05 covers them.
- Destination acceptance, and any bed or stock hold at the destination. Arrival is the only confirmation.
- Moving stock with the patient. Blood and equipment stay on the stock transfers (B01 to B03).
- Changing the destination of an open request. Cancel it and request again.
- Notifications to either hospital (B06, B07). For now the incoming panel is how the destination finds out.
- Patient identity. None is stored or shown.
- Transfer reports (B18).

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **Re-estimate the bolt from 11 to 5 points?** The backlog gave #63, #64 and #65 3, 5 and 3 points (11 in all, in `scripts/backlog.py`). Proposed: keep 5. The flag and the destination list are mostly built (#33, #42), and the new work is one model, the arrival move and its tests. That holds only for the scope above. If the destination must accept first (question 3), or the sending hospital keeps read access (question 5), estimate about 8.
2. **Which severities raise the flag?** #63 says "critical requirements". Proposed: critical cases only. A high case is "needed within a few hours" (the severity hint), so a slower move may do for it. The PO can add high later as a one-line change.
3. **Must the destination accept before the patient moves?** Proposed: no. B17 has no acceptance step: the sending hospital decides, and the destination confirms arrival. An acceptance step can follow.
4. **What happens to stock at the sending hospital on arrival?** Proposed: unallocated holds are released, unanswered stock requests are cancelled, and approved, dispatched or in-transit ones block arrival until they finish.
5. **Does the sending hospital keep read access after arrival?** Proposed: no. The case leaves its list, and its outgoing row (arrived, with destination and time) stays visible. Read access would show the destination's stock as the case's local availability, and that stock is not theirs to see.
6. **Can a case with nothing short be moved?** Proposed: no. The move answers a shortfall. A move for another reason, such as specialist care, is a later bolt.

## Approval

- [x] Approved by: Krrishna on 2026-11-18 (proposed answers accepted as written)
