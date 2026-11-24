# Construction Plan: Patient privacy safeguards (HIPAA principles)

**Spec:** [docs/aidlc/inception/2026-11-23-patient-privacy.md](../inception/2026-11-23-patient-privacy.md)
**Date:** 2026-11-23

## Units of work

| Unit | Description | Files touched | Tests |
|---|---|---|---|
| 1 | The rule in one place: `sees_patients` and `sees_case_patient`, used by the serializers that carry patient fields (beds, cases, case detail notes and outcome, theatre bookings, patient transfers) | `apps/accounts/permissions.py`, `apps/hospitals/serializers.py`, `apps/emergencies/serializers.py`, `apps/operating_rooms/serializers.py`, views that pass the user | Role by role per endpoint; another hospital's admin; the CityCare admin; the receiving hospital once the move is asked |
| 2 | A record of access: `record_view` (`phi.view`, 10-minute window in the shared cache), called where patient details are shown; the audit log hides other hospitals' patient text in its list and export | `apps/audit/services.py`, `apps/audit/views.py`, the views above, `queue_views.py` | Once per window; none when nothing was shown; filterable; redaction in list and export |
| 3 | The coverage check: every API list read by every role outside the rules carries no patient marker; notifications carry references and tags only | `apps/core/tests/test_privacy.py` | The sweep; the notification check |
| 4 | The site: hidden fields handled, the receiving hospital sees who is coming, the public **Patient privacy** page with the owner's HIPAA statement and each safeguard, linked from the footer | `frontend/src/pages/PrivacyPage.tsx`, `api/emergencies.ts`, `features/emergencies/IncomingPatients.tsx`, `SiteFooter.tsx` | The page's statement and safeguards; the footer link |
| 5 | Docs: the privacy review (inventory, safeguards, tests, residual risks), the user manual's privacy section, the API note | `docs/testing/privacy-review.md`, `docs/setup/user-manual.md`, `docs/architecture/api.md` | Board and deploy checks |

Refinements of the spec, settled while building:

- Doctors and nurses without a hospital still match records without one (data from before Sprint 2), as the
  own-hospital rule always has; an admin must have the record's hospital, so the CityCare admin sees no patient.
- Allocation notes stay visible to everyone who sees the case: the allocating blood bank writes them, about the stock.
- The audit log was network-wide for every admin (B10), so entries about a case, a patient transfer or an emergency
  visit now hide their free text from those who may not see that patient.
- Two B22 details fixed on the way: the theatre chart's table showed UTC times, and its summary counted cancellations
  the schedule doesn't return.

## Test plan

AGENTS.md checks, the deploy-config and board checks, and the e2e scenario against a fresh seed.

## Review

The PR needs a reviewer's approval per [CONTRIBUTING.md](../../../CONTRIBUTING.md).
