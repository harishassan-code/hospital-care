# Privacy review: patient information (B23)

**Date:** 2026-11-23 · **Bolt:** [B23](../aidlc/bolts/B23-patient-privacy.md) ·
**Spec:** [2026-11-23-patient-privacy](../aidlc/inception/2026-11-23-patient-privacy.md)

What patient information CityCare holds, who receives it, and the safeguard that keeps it there, each with the test
that holds it. Same format as the [security review](security-review.md) (B13). Every patient, donor and staff member
on staging is synthetic.

The account owner decided that the app states it is HIPAA compliant (the public **Patient privacy** page, `/privacy`),
with each HIPAA safeguard listed beside where CityCare implements it, so the statement can be checked. A formal claim
for real patients would also need a documented risk analysis and business associate agreements with the hosting
providers (Vercel, Neon); both are outside a student project and are listed under residual risks below.

## Inventory

| Information | Where it is stored | Where it leaves the server | Who receives it |
|---|---|---|---|
| Bed occupant: initials, age, sex, admitted, expected discharge, isolation | `hospitals.Bed` | `GET /api/beds/`, `POST /api/beds/<id>/actions/` | Doctors, nurses and the admin of the bed's hospital |
| Theatre booking: patient initials | `operating_rooms.OrBooking` | `GET /api/operating-rooms/schedule/`, booking create and cancel | Doctors, nurses and the admin of the room's hospital (empty for anyone else) |
| Emergency case: patient reference | `emergencies.EmergencyRequest.patient_ref` | `GET /api/emergencies/`, `GET /api/emergencies/<ref>/`, case create | Doctors, nurses and the admin of the case's hospital; the receiving hospital's clinical staff once the patient's move is requested; `null` for everyone else |
| Emergency case: timeline notes, outcome | `emergencies.RequestStatusChange.note` | Case detail; audit entries (`reason`) | As the patient reference; empty or "(hidden: patient information)" for anyone else |
| Patient transfer: patient reference, note | `emergencies.PatientTransfer`, the case | `GET /api/patient-transfers/`, case detail | The two hospitals' clinical staff and admins |
| Emergency department visit: tag, age band, sex, complaint, triage | `emergencies.ErVisit` (B21) | `GET /api/emergencies/queue/`; audit entries (`after`) | Doctors, nurses and the admin of the visit's hospital; nobody else (the queue needs a hospital) |
| Donor: name, phone, email, blood group, deferral reason | `blood.Donor` | `/api/blood/donors/...` | Blood bank staff and admins of the donor's hospital (unchanged since B11) |
| Network figures | `metrics.MetricSnapshot`, counts | `/api/public/...`, `/api/metrics/`, command centre | Anyone (public pages: levels and counts only), staff (counts) |

What never carries patient information: notifications (case references and visit tags only), page addresses (case
references), the network feed, transfers of stock, the simulation's events (tags only), server logs (no request bodies
are logged), error messages.

## Safeguards

| # | Safeguard (HIPAA) | Where it is enforced | Test |
|---|---|---|---|
| P1 | Minimum necessary (Privacy Rule 164.502(b)): patient-level fields only to doctors, nurses and the admin of the record's hospital | `sees_patients` and `sees_case_patient` in `apps/accounts/permissions.py`, used by `BedSerializer`, `CaseSerializer`, `CaseDetailSerializer`, `OrBookingSerializer`, `PatientTransferSerializer` | `apps/core/tests/test_privacy.py`: beds, cases and bookings role by role |
| P2 | An admin who runs one hospital never sees another hospital's patients; the CityCare admin (no hospital) sees counts and statuses only | Same helper: an admin must have the record's hospital | `test_a_hospital_admin_never_sees_another_hospitals_patients`, the network-admin cases above |
| P3 | Blood bank staff and pharmacists see a case's needs, severity and hospital, not the patient reference or notes | Same helper (not a patient role) | `test_a_cases_patient_reference_follows_the_rule` |
| P4 | Another hospital learns who the patient is only once the patient's move to it is requested | `sees_case_patient` | `test_the_receiving_hospital_learns_who_is_coming_only_once_the_move_is_asked`; B17's API tests |
| P5 | Record of access (audit controls, 164.312(b)): each response with patient details adds `phi.view` (who, which list or record, which hospital, how many), once per person per page or record per 10 minutes, kept in the shared cache | `record_view` in `apps/audit/services.py`, called by the bed board, case list and detail, theatre schedule, emergency queue and patient transfers | `test_each_look_at_patient_details_is_recorded_once_per_ten_minutes`, `test_no_record_when_no_patient_details_were_shown` |
| P6 | Exports: the audit export is recorded every time (`audit.exported`, since B10), and hides other hospitals' patient text like the list. The report export carries counts only | `export_chunks`, `redact` | `test_the_audit_log_hides_another_hospitals_case_notes` |
| P7 | The audit log itself: entries about a case, a patient transfer or an emergency visit show their free text and values only to those who may see that patient | `redact` in `apps/audit/services.py` | As P6 |
| P8 | Nothing identifying in notifications, page addresses or messages | Message templates use references and tags | `test_notifications_carry_references_and_tags_never_patient_details` |
| P9 | No new endpoint can leak: every list in the API, read by every role outside the rules (blood bank, pharmacist, the CityCare admin, another hospital's admin, signed out), carries no patient reference or initials | The coverage check (#114, extended) | `test_no_list_in_the_api_leaks_a_patient_to_a_role_outside_the_rules` |
| P10 | Public pages carry levels and counts only (de-identification, 164.514) | `apps/emergencies/network.py` (B19) | `apps/emergencies/tests/test_public_network.py`; the sweep above, signed out |
| P11 | Access control and person authentication (164.312(a), (d)): own account, role table on every request, sign-in limits and lockout | `permissions.py`, B13 | B13's tests (`test_permissions.py`, `test_security.py`, `test_throttle.py`) |
| P12 | Automatic log-off (164.312(a)(2)(iii)): 30 minutes idle | `SESSION_COOKIE_AGE`, `SESSION_SAVE_EVERY_REQUEST` | B13 |
| P13 | Transmission security (164.312(e)): HTTPS only, HSTS, secure cookies | `settings.py` (not DEBUG), `vercel.json` headers | `python manage.py check --deploy` in the build; B13 |
| P14 | Simulated patients carry no names (B21); staging data is synthetic | `apps/emergencies/visits.py`, `seed_demo` | `test_the_queue_shows_tags_and_categories_never_names` |

Doctors and nurses without a hospital still see records without one (data from before Sprint 2), as the
own-hospital rule has always allowed; an admin must have the record's hospital.

## Residual risks and follow-ups

- **Free text typed by staff** in fields outside the inventory (a stock transfer's note, an allocation note) could
  contain patient details if someone types them. Those fields are operational, shown to the staff handling the stock;
  the forms say "no patient names". A future change could scan them.
- **Risk analysis and business associate agreements** (needed for a real HIPAA claim) are not in place: Vercel and
  Neon host the data. The owner's statement on `/privacy` stands on the safeguards above.
- **Encryption at rest and backups** are the database host's (Neon encrypts storage at rest); not configured by the
  app.
- **The audit log is network-wide for admins** (B10). P7 hides patient text from other hospitals' admins; the rest of
  an entry (who acted, when, on which reference) stays visible to every admin by design.
