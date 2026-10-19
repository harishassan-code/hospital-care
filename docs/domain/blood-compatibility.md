# Blood compatibility rules

**Scope:** CityCare is a coordination aid, not a clinical decision-maker. It uses these rules to find and rank
units that *may* suit a patient. The hospital laboratory still confirms every transfusion (group and screen,
crossmatch), and clinicians decide on any exception below.

**Source:** Australian Red Cross Lifeblood, *Component compatibility*,
<https://www.lifeblood.com.au/health-professionals/products/component-compatibility> (page last updated
April 2026, accessed 13 Oct 2026). Lifeblood is Australia's national blood service. The tables below copy its
ABO choices. "System rule" is the stricter subset the software applies automatically.

## Red cells

| Patient ABO | Best option | OK to use | Never use |
|---|---|---|---|
| O | O | – | A, B, AB |
| A | A | O | B, AB |
| B | B | O | A, AB |
| AB | AB | O, A, B | – |

**RhD:** RhD-negative patients should receive RhD-negative red cells. Lifeblood allows RhD-positive red cells for
RhD-negative males over 18 and females over 50 *when necessary*, accepting the risk of anti-D. That is a clinical
call, so the system never offers it automatically.

**System rule:** a donor unit may carry no ABO antigen the patient lacks, and an RhD-negative patient gets only
RhD-negative units. This is what `compatibleDonors(recipient, 'redCells')` in
`frontend/src/features/blood/blood.ts` implements.

**Emergency, group unknown (Lifeblood):** O RhD-negative for females ≤ 50 and males ≤ 18; O RhD-negative or
O RhD-positive for everyone else.

## Plasma (FFP)

The direction reverses: donor plasma carries antibodies, so the donor's ABO antigens must cover the patient's.
AB plasma suits every patient. RhD does not apply.

| Patient ABO | 1st choice | 2nd | 3rd | 4th |
|---|---|---|---|---|
| O | O | A | B | AB |
| A | A | AB | – | – |
| B | B | AB, or low-titre A\* | – | – |
| AB | AB | low-titre A\* | – | – |
| Unknown, adult | low-titre A\* | AB | A | – |
| Unknown, neonate | AB | low-titre A\* | A | – |

\* Low-titre group A plasma is ABO-*incompatible* for B and AB patients. Lifeblood lists it because the low
antibody titre lowers the haemolysis risk. The system does not record titres, so it does not offer these
options.

**System rule:** ABO-compatible plasma only, i.e. `compatibleDonors(recipient, 'plasma')`.

## Platelets

| Patient ABO | Best option | Acceptable | Emergency, group unknown |
|---|---|---|---|
| O | O | A, B | O or A |
| A | A | B, O | O or A |
| B | B | A, O | O or A |
| AB | AB | A, B, O | A or B |

Lifeblood notes that low-titre anti-A/B platelets lower the haemolysis risk, and that RhD-positive platelets for
an RhD-negative female of childbearing potential need RhD immunoglobulin.

**System rule (proposed for Sprint 6 matching):** rank ABO-identical first, then the "acceptable" groups.
Flag any RhD-positive platelet offered to an RhD-negative patient so a clinician can arrange anti-D cover.

## Cryoprecipitate

Lifeblood's page gives no cryoprecipitate table. Until the team cites a source for it, the system applies the
plasma rule to cryo.

## Where the rules live

- Frontend: `compatibleDonors()` in `frontend/src/features/blood/blood.ts` (red cells and plasma).
- Backend: the matching engine (Sprint 6, issue #37) must load these as configurable rules, not hard-code a
  second copy.
