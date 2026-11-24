# Inception Spec: Patient privacy safeguards (HIPAA principles)

**Date:** 2026-11-23
**Author:** Haris Hassan (Claude, drafted for review)
**Bolt:** [B23](../bolts/B23-patient-privacy.md)
**Related backlog item:** the account owner's request of 23 Nov (a GitHub issue is opened when this is approved)

## Problem

CityCare moves patients' needs between hospitals, and B21 adds a live emergency queue. Patient information must reach
only the people who need it for their work, and stay out of everything public. Today the rules are per module (the
access table) and per hospital (`own_hospital`), which covers most of it, but nobody has listed every place patient
information appears, some roles see more than they need (for example, blood bank staff and pharmacists can open an
emergency case with its patient reference), and nothing records who looked at patient-level data.

HIPAA (US) is the best-known set of rules for this: its Privacy Rule's *minimum necessary* standard, and its
Security Rule's access control, audit controls, automatic sign-off and transmission security. CityCare is a student
project in Pakistan and not a HIPAA covered entity, so it can't claim compliance; it can follow the same principles
and show how.

For: patients (whose information it is), every staff role, the Product Owner.

## User stories

- As a patient, I want my information seen only by the staff treating me, so that my privacy is respected.
- As a hospital administrator, I want a record of who viewed patient information, so that misuse can be found.
- As any staff member, I want to see what my job needs and nothing more, so that I can't leak what I never had.

## Acceptance criteria

- [ ] **Inventory** in `docs/testing/privacy-review.md`: every field that is patient information (bed occupant
      initials, sex, age, admission and discharge dates, isolation; operating room booking initials; emergency case
      patient reference and notes; emergency department visits from B21: tag, age band, sex, complaint, triage;
      patient transfers) and donor personal data (names, phones, emails, deferral reasons), with every endpoint,
      export, notification and audit entry that carries it, and the roles that receive it.
- [ ] **Minimum necessary**, enforced on the server and tested per endpoint and role:
  - patient-level fields go to the roles that treat patients (doctor, nurse) and to the admin of the same hospital;
  - blood bank staff and pharmacists see what they need from a case (its items, severity, hospital) but not the
    patient reference or notes;
  - other hospitals see a case's needs and status, and the patient reference only once a patient transfer to them
    is requested;
  - donors' personal data stays with blood bank staff (as today);
  - public endpoints carry levels and counts only (B19).
- [ ] **Record of access:** each response that includes patient-level data adds an audit entry (`phi.view`: who,
      which list or record, which hospital, how many records), at most once per person per endpoint per 10 minutes,
      so polling doesn't flood the log. Admins can filter the audit log by it. Exports with patient data are recorded
      every time.
- [ ] **Nothing identifying in the wrong places:** notifications, page addresses (URLs), server logs and error messages
      use case references and tags, never initials or details. A test checks the notification messages.
- [ ] **Already in place and re-checked:** sign-out after 30 minutes idle, HTTPS only with HSTS, secure cookies,
      sign-in limits and lockout (B13); simulated patients carry no names (B21).
- [ ] The extended API permission coverage test (#114) fails if a new endpoint returns patient fields to a role
      outside the rules.
- [ ] User manual: a short "Patient privacy" section saying what each role sees and that views are recorded.

## Design

- A `PatientDataAccess` helper in `apps/accounts/permissions.py`, beside `own_hospital`, used by the serializers
  that carry patient fields to drop them for roles that may not see them, so each view doesn't repeat the rule.
- `apps.audit.services.record_view(actor, kind, hospital, count)` with the 10-minute window kept in the database
  cache (shared across copies on Vercel).
- The privacy review follows the B13 security review's format: each safeguard, where it's enforced, its test.

## Non-goals

- Legal compliance or certification; encryption at rest and backups (the database host's); patient consent records.

## Open questions

Proposed answers; the account owner confirms them at sign-off:

1. **How do we word it?** *Proposed:* "follows the privacy and security principles of HIPAA", never "HIPAA
   compliant". HIPAA is US law and CityCare isn't a covered entity.
2. **How often is a view recorded?** *Proposed:* once per person per endpoint per 10 minutes, and every export, so
   the record is useful without flooding the audit log with the 30-second refresh.
3. **What does a network admin with no hospital see?** *Proposed:* counts and statuses across the network, but
   patient-level details only at a hospital they belong to. Today such an admin sees everything; this narrows it,
   and the command centre keeps working because it uses counts.

## Decisions at sign-off, 23 Nov

- **Q1 (wording):** the account owner decided that the app states it is HIPAA compliant, and that the practices are
  built in regardless. The privacy page lists each HIPAA safeguard and where the app implements it, so the statement
  can be checked. (A formal compliance claim for real patients would also need a documented risk analysis and business
  associate agreements with the hosting providers; that is outside a student project and noted in the privacy review.)
- **Q3 (admins):** confirmed and widened by the account owner. An admin who runs one hospital (an owner or manager)
  sees patient information only for that hospital, never another hospital's. The CityCare admin (no hospital) sees
  counts and statuses across the network, and no patient-level details.

## Approval

- [x] Approved by: Haris Hassan (`harishassan-code`, account owner) on 2026-11-23, with the decisions above
