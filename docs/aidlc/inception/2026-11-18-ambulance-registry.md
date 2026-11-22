# Inception Spec: Ambulance registry

**Date:** 2026-11-18
**Author:** Krrishna
**Bolt:** [B04](../bolts/B04-ambulance-registry.md)
**Related backlog item:** #50 Ambulance registry (Epic E6, Sprint 8; [issue](https://github.com/harishassan-code/hospital-care/issues/50)).
Builds on the equipment registry (#26, same shape) and the [shared resource model](../../architecture/resources.md).
Ambulances are used by the transfers in [B01](2026-11-18-transfer-request.md) and [B02](2026-11-18-transfer-tracking.md),
and dispatched in B05.

## Problem

The platform tracks beds, blood, equipment and operating rooms, but not ambulances. A coordinator cannot see how many
ambulances a hospital has, what type each one is, or which ones are available. So nobody can tell whether a transfer
can be moved. The `/staff/ambulances` page is still a placeholder.

This is for the emergency coordinator (a doctor or nurse), who needs to see transport capacity. It is also for the nurse
or admin who keeps the registry up to date at each hospital.

## User stories

- As a coordinator, I want ambulances registered with their base hospital and type, so that transport capacity is known. (#50)

## Acceptance criteria

**Model and admin**

- [ ] New app `backend/apps/ambulances/`, in `INSTALLED_APPS`, with its API under `/api/ambulances/`. Same layout as
      `apps/equipment/`.
- [ ] An ambulance is a `Resource`. It has an identifier, a type, a base hospital (the inherited `hospital` field) and a
      status.
- [ ] The identifier (for example `AMB-04`) is trimmed and stored in upper case. It is unique per hospital, ignoring case,
      by a database constraint.
- [ ] Types: `basic` (Basic life support), `advanced` (Advanced life support) and `patientTransport` (Patient transport).
- [ ] Statuses: `available`, `maintenance` and `outOfService`. A new ambulance starts as `available`.
- [ ] Status moves go through a `StateMachine` in `apps/ambulances/models.py`, applied by `change_status`
      (`apps.resources.services`) inside `transaction.atomic()` with `select_for_update()`, as `apply_equipment_action` does.
- [ ] The Django admin lists ambulances, with filters for type, status and hospital.

**API**

- [ ] `GET /api/ambulances/` with optional `type`, `status` and `q` (matches the identifier) returns the ambulances of the
      user's hospital. Admins get all hospitals. Each item has `id`, `identifier`, `type`, `status`, `statusSince` and
      `hospital` (the name), as in the equipment API.
- [ ] `POST /api/ambulances/` registers one. Non-admins register at their own hospital. Admins send `hospitalId`.
      Success is 201 with the new ambulance. A duplicate identifier at that hospital is 400 `{"identifier": [...]}`.
      No hospital to use is 400 `{"hospitalId": [...]}`. A 400 saves nothing.
- [ ] `POST /api/ambulances/<id>/actions/` with `{"action": "...", "reason": ""}` (reason optional) makes one of the moves
      in the rules table. Success is 200 with the ambulance. A move the status does not allow is 409 with the machine's
      message (for example "Can't outOfService a vehicle that is out of service."), and nothing changes.
- [ ] Access: 403 for a signed-out user, for a role with no access to `ambulances`, and for a view-only role that sends a
      POST. 404 for an unknown id, and for another hospital's ambulance when the user is not an admin.
- [ ] Every change writes an audit record through `apps.audit.services.record`: `ambulance.registered` on register, and
      `ambulance.status_changed` on each move (written by `change_status`).

**Permissions**

- [ ] `ambulances` is added to `ACCESS` in `backend/apps/accounts/permissions.py` and to `Module` and `ACCESS` in
      `frontend/src/features/staff/roles.ts`, with identical rows (see the rules table). `docs/architecture/api-contracts.md`
      gets an `ambulances` column.

**Page**

- [ ] `/staff/ambulances` replaces the placeholder. It shows a table (`aria-label="Ambulances"`) with asset tag, type, base
      hospital and status. Above it, "N of M available right now", and filters for type and status.
- [ ] Users with edit see **Register ambulance** (asset tag, type, and a base hospital select for admins) and one button per
      move allowed from the current status. View-only users see the table and no buttons.
- [ ] After a move the row shows the server's copy and the change is announced. A 409 reloads the list and says the status
      changed first. A 403 says the role can't change ambulances. This follows the equipment page.
- [ ] The nav item **Ambulances** shows for admin, doctor and nurse. It is hidden for blood bank and pharmacist.
- [ ] `/staff/ambulances` is removed from `frontend/src/features/staff/planned.ts`.

**Seed and tests**

- [ ] `seed_demo` adds two ambulances per seeded hospital (one `advanced`, one `basic`) and one `patientTransport` at the
      main hospital: 7 in all. A re-run adds only the missing ones, per hospital. `--reset` deletes them.
- [ ] Backend tests in `backend/apps/ambulances/tests/` cover: list filters and own-hospital scope; register 201 and the 400
      cases; each action's 200 and 409; 403 for signed-out users, roles without edit and view-only POSTs; 404 across
      hospitals.
- [ ] `frontend/src/test/mockApi.ts` mocks the new endpoints in the real shape. The page test covers filters, and the
      register form and move buttons for an editor and a view-only user.

**Docs**

- [ ] `docs/architecture/erd.md` names the Ambulance fields as built here (`identifier`, `type`, `hospital`, `status`). It
      currently says `code` and `base_hospital`.

## The rules in one place

| Thing | Rule |
|---|---|
| Base hospital | `Resource.hospital`. Non-admins register at their own hospital; admins choose one. The model keeps it nullable, as `Resource` does; the API always sets it. |
| Who can see | `ambulances` view: admin, doctor, nurse. Blood bank and pharmacist: none. |
| Who can change | `ambulances` edit (register and moves): admin, nurse. Doctor is view only. Admins: any hospital. Everyone else: own hospital only. |
| Identifier | Trimmed, upper case, unique per hospital, ignoring case. |
| Type | `basic`, `advanced`, `patientTransport`. |
| Status | `available` (label "Available"), `maintenance` ("In maintenance"), `outOfService` ("Out of service"). New ones start `available`. |
| Moves | `startMaintenance`: available → maintenance. `finishMaintenance`: maintenance → available. `outOfService`: available or maintenance → outOfService. `returnToService`: outOfService → maintenance. The same moves as equipment, without the in-use states that B05 adds. |
| Not found | Another hospital's ambulance, for a non-admin: 404, as `apply_equipment_action` does. |
| Audit | `ambulance.registered`, `ambulance.status_changed`. |
| 409 wording | Noun "vehicle", so the message reads "Can't … a vehicle that is …". |

## Non-goals

- Dispatch, trips and the "on trip" status. That is [B05](../bolts/B05-ambulance-dispatch.md) (#51), which adds the status
  and its moves.
- Make and model, capacity, crew, equipment on board, GPS and ETAs.
- Editing or deleting a registered ambulance. A wrong identifier or type is fixed in the Django admin for now.
- Staff at one hospital seeing ambulances at other hospitals (see open question 3).
- Notifications when a status changes (B06, B07). Import from a file. Maintenance schedules and service history.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **New `apps/ambulances` app, or inside `apps/transfers`?** Proposed: its own app, like equipment. Reason: B05 adds trips
   to transfers, and the registry should not depend on transfers.
2. **Ambulance types: basic, advanced life support, or patient transport?** Proposed: all three as `basic`, `advanced` and
   `patientTransport`. Reason: they are the three the bolt names, and a fourth is one new choice later.
3. **Can staff see ambulances at other hospitals?** (Added in this spec.) Proposed: not in B04. The list shows the user's
   hospital, and admins see all, as equipment does. Reason: nothing in B04 needs a network view. B05 can widen the list
   when a transfer needs an ambulance from elsewhere.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
