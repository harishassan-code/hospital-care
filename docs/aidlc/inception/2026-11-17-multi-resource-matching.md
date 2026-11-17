# Inception Spec: Multi-resource matching

**Date:** 2026-11-17
**Author:** Krrishna
**Related backlog item:** #42 Multi-resource matching (Epic E4, Sprint 6; builds on
[#33 Local availability check](2026-11-17-local-availability-check.md),
[#38 Find candidate hospitals](2026-11-17-find-candidate-hospitals.md) and
[#41 Ranked results with explanation](2026-11-17-ranked-results-with-explanation.md). Stock claims are #45.)

## Problem

A critical case often needs several things at once: an ICU bed, a ventilator and blood. The sources list (#38, #41)
ranks the hospitals for each need on its own. So a coordinator who wants to send the patient to one place has to read
several lists and work out which hospital has all of them. A hospital with two of three needs can sit above the one
with all three, because each need is ranked alone.

The coordinator needs one answer to "where can this patient go and get everything?", and, when no hospital has
everything, to see what each hospital is missing.

## User stories

- As a coordinator, I want hospitals that satisfy several requirements at once ranked higher, so that patients go where
  everything is available. (#42)

## Acceptance criteria

- [ ] Hospitals that meet every short need rank above hospitals that meet only some of them, whatever their scores.
- [ ] Among hospitals that meet only some needs, the one that meets more of them ranks higher.
- [ ] Each partial match lists the needs it does not meet, with how many are missing for each.
- [ ] A partial quantity shows as unmet, with how many the hospital has ("only 1 of 2").
- [ ] Two needs that draw on the same stock at one hospital (two O− red-cell lines, two ICU bed lines) are judged
      together: a hospital with stock for one of them does not cover both.
- [ ] The order is deterministic, and "Recommended" is shown only for a hospital that has everything.
- [ ] A case with one short need shows no multi-resource section, because the per-need ranking already answers it.
- [ ] The candidates request makes the same number of database queries as it did under #41.

## Design decisions

- **Built on the candidates that already exist.** `match_hospitals` reads the output of `candidates_for_case` (#38) and
  adds no query. It works out, for each hospital that appears as a candidate for at least one short need, which needs it
  covers and which it does not.
- **Coverage is judged per stock.** Needs that draw on the same stock at a hospital share its count. The first need in
  the case's item order is covered first; the next sees what is left. This is the same rule the local check uses (#33),
  applied to the other hospitals.
- **The order.** Complete first. Then the number of needs covered, most first. Then the score, highest first. Then the
  distance, nearest first (no distance last). Then the hospital id, so ties are stable.
- **The score.** A hospital's score is the mean of its per-need scores from #41, over the needs it has candidates for,
  to one decimal. It breaks ties; it does not decide whether a hospital is complete.
- **Recommended.** `recommended` is `true` only on rank 1, and only when that hospital is complete. A partial match is
  never recommended.
- **The API extends the candidates endpoint.** `GET /api/emergencies/<ref>/candidates/` gains a top-level `hospitals`
  list. The `items` part is unchanged.
- **The screen.** A "Best single destination" section sits above the per-need sources, only when the case has two or
  more short needs. A complete hospital is labelled "Has everything", and the top complete one "Recommended", as text
  badges. A partial one lists what it is missing. When no hospital is complete, a line says so and points to the per-need
  sources.

## Known limits

- **Blood donors across groups.** Candidates for blood are grouped per need: the compatible units for each group and
  component. Two needs with different groups (O− and A+ red cells) can both count the same O− unit at a hospital, so the
  judgement can overstate what a hospital can give. Allocation (#45) resolves this exactly. It is not solved here.
- **Operating rooms with two capabilities.** A room that serves both cardiac and general counts for each capability's need.
  The same room can be counted twice across needs of different capabilities. The fix needs room ids in the candidates,
  which is a query change, so it waits for #45.

## Non-goals

- Reserving, requesting or allocating stock at the recommended hospital. **#45.**
- Changing the scoring rules, weights or defaults. Those are #40.
- Sorting on the client, or any ordering the server does not produce.
- A new endpoint, a new setting, or a stored result. Nothing is written to the database.
- Showing the multi-resource section on the feed or on any screen other than the case page.

## Open questions

Proposed answers; the Product Owner confirms them at sign-off:

1. **A complete hospital with a score of 0 is recommended.** Proposed: yes. The acceptance criterion says "Recommended"
   only for a hospital that has everything, and a score of 0 on the per-need scores (for example, only distance counts and
   the hospital is beyond the maximum distance) is a property of the strategy, not a sign the hospital cannot help. The
   alternative is to add #41's rule (score above 0) here as well.
2. **The score of a partial hospital is the mean over the needs it has.** Proposed: yes, because coverage already decides
   the order between partial hospitals. The alternative is to count a need the hospital has nothing for as 0, which would
   lower the score of every partial hospital by its missing needs.
3. **The section is hidden for one short need.** Proposed: yes, as the story says. The per-need list already gives the
   ranking for a single need, and a second table would repeat it.

## Approval

- [ ] Approved by: pending (Product Owner, via PR review)
