# Inception Spec: Blood compatibility matching engine

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** [#37 Blood compatibility matching engine](https://github.com/harishassan-code/hospital-care/issues/37) (Epic E5, Sprint 6)

## Problem

Local availability (#33) counts only blood of the exact group the case needs, and says that cross-group
compatibility is this story's job. The rules themselves are written down in
[docs/domain/blood-compatibility.md](../../domain/blood-compatibility.md), and the frontend applies the red-cell
and plasma rules in `compatibleDonors()`. Nothing on the backend applies them, so there is no way to ask the
network for every usable unit that may suit a patient.

## User stories

- As a hospital, I want the system to find compatible, approved, unexpired, unreserved units across the network,
  so that blood is located quickly.

## Acceptance criteria

- [ ] The compatibility rules are loaded from a documented configuration file,
      `backend/apps/matching/blood_compatibility.json`. It copies the "System rule" lines of
      `docs/domain/blood-compatibility.md`, and its header points to that document.
- [ ] A broken rules file fails `manage.py check` with a message that says what is wrong, and the first load
      raises the same message.
- [ ] Only usable units count: status `available` and not past expiry. Untested (quarantined), reserved, issued,
      discarded, expired-status and expired-by-date units are left out.
- [ ] Units from every hospital in the network are found. The requesting hospital can be excluded.
- [ ] Results are ordered by donor preference, then earliest expiry first.
- [ ] Unit tests cover every ABO/Rh combination for each component: 4 components x 8 recipient groups x 8 donor
      groups.
- [ ] Red cells and plasma agree with the frontend's `compatibleDonors()`. A test in the frontend fails if they drift.

## Rules applied

These follow the "System rule" lines of the domain doc, with the preference order set by this spec.

- **Red cells:** the donor carries no ABO antigen the recipient lacks. An RhD-negative recipient gets only
  RhD-negative units. Order: the identical group, then the same ABO group with the other RhD, then the other
  compatible ABO groups (A, then B), then O+ and O-. O- is last, as the universal reserve.
- **Plasma:** ABO-compatible only. The donor's antigens must cover the recipient's, so AB plasma suits everyone. RhD
  does not apply. Order follows the doc's 1st to 4th choice columns, with the RhD-matching group first in each ABO
  tier. Low-titre group A options are left out, as the doc says the system does not offer them.
- **Platelets:** the ABO-identical group first, then the doc's "Acceptable" groups. An RhD-positive platelet offered
  to an RhD-negative recipient is allowed but flagged, so a clinician can arrange anti-D cover.
- **Cryoprecipitate:** the plasma rule. The doc gives no cryo table, so this applies until a source is cited.

## Non-goals

- **No API endpoint and no UI.** Candidate search (#38) and ranked results (#41) are the consumers. This story
  delivers a backend engine with a queryset, so those stories can build on it.
- **Not a crossmatch and not a clinical decision.** The hospital laboratory still confirms every transfusion, and
  clinicians decide any exception.
- **Emergency "group unknown" options are not encoded.** They describe what to give when the patient's group is
  unknown, not a recipient group.
- **No anti-D exception for RhD-positive red cells.** The doc calls this a clinical call, so the system never offers it.
- **No change to `compatibleDonors()`, to the distance module (#39) or to local availability (#33).** The frontend
  test checks the rules file against `compatibleDonors()` and does not replace it.
- **No hospital partnership or network scope.** Every hospital's usable units are eligible, minus the one excluded
  id.

## Open questions

- **Red-cell order for AB patients.** The doc lists O first for AB patients ("OK to use O, A, B"). The spec puts O-
  last, as the universal reserve. Confirm the spec's order, or use the doc's.
- **Order within an ABO tier.** This spec puts the patient's RhD sign first, then the other. Confirm.
- **Platelet flag.** The flag is set only for an RhD-positive platelet to an RhD-negative patient, as the doc says.
  Confirm that a flagged unit should still rank in its normal place rather than drop.
- **Cryoprecipitate.** The plasma rule stands until the team cites a cryo source.

## Approval

- [ ] Approved by: _pending (Product Owner, via PR review)_
