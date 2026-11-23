---
id: B23
title: Patient privacy safeguards (HIPAA principles)
issues: -
points: 3
priority: high
sprint: 9
depends_on: -
owner: harishassan-code
status: In Progress
---

# B23 · Patient privacy safeguards (HIPAA principles)

**Goal:** Patient information reaches only the staff who need it for their work at that hospital, every view of it
is recorded, and nothing that identifies a patient appears anywhere public, checked against HIPAA's safeguards.

## Stories and acceptance criteria

From the account owner's request of 23 Nov:

- [ ] HIPAA rules followed, so no sensitive information reaches anyone other than the people authorised to handle it.

## Build on

- `apps/accounts/permissions.py` (`module_permission`, `own_hospital`), the API permission coverage test (#114),
  the B13 security review (`docs/testing/security-review.md`), `apps.audit`.

## Scope

- **In:** an inventory of patient fields and endpoints, minimum-necessary rules per role, a record of who viewed
  patient-level data, tests per endpoint and role, a privacy review document.
- **Out:** encryption at rest and backups (the host's), legal compliance.

## Open questions for Inception

- How do we word it, given HIPAA is US law and this is a student project?
- How often is a view recorded?
- What does a network admin (no hospital) see?

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/2026-11-23-patient-privacy.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/2026-11-23-patient-privacy.md` written
- [ ] Code, tests and docs merged; CI green; Definition of Done met
- [ ] Operations notes `docs/aidlc/operations/2026-11-23-patient-privacy.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated, issue(s) closed
