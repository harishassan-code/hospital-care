# Sprint 8 Retrospective

**Date:** Fri 27 Nov · **Format:** Start / Stop / Continue · **Attendees:** _at the retro_

> **Prepared record.** The last sprint's action item and the points from the record were filled in on 23 Nov 2026
> from the GitHub history, so the retro can start from facts. What went well, what didn't, the action items and the
> mood are the team's to write at the retrospective; nothing here is a team conclusion until then.

## Last sprint's action items

| Action | Owner | Done? | From the record |
|---|---|---|---|
| Smaller PRs merged within the sprint | each developer | _at the retro_ | All seven committed stories reached `main` on day 2 of the sprint, but in one PR (#104) rather than one per story. The stretch and Sprint 9 work came as one PR per bolt (#106–#112) |

## From the record, for discussion

Facts from Sprint 8's history (to 23 Nov), with the change each suggests. The final report's lessons learned list most of them
([section 5](../final/final-report.md#5-lessons-learned)):

- **Everything committed was on `main` by 22 Nov,** with 22 stretch points and the end-to-end scenario (#57). It's
  the first sprint whose review can demo all of its work from `main`.
- **Two implementations of the ambulance bolts were opened** (#104 and #110; #110 was closed). Suggests: claim a bolt
  on the board (`owner:`) before starting work on it.
- **The six PRs that followed #104 all conflicted** with `main` and with each other, and were merged one at a time
  with each conflict fix tested. Suggests: rebase on `main` daily while a PR is open.
- **Two timing-dependent frontend tests turned `main` red at random** until #115 and #120 fixed them. Suggests: treat
  a flaky test as a bug on the day it appears.
- **Squash-merging a PR that carries other people's commits credits all of its lines to the person who opened it.**
  Suggests: merge integration PRs with a merge commit.
- **Some specs were signed by their own author.** Suggests: someone other than the author signs the spec gate.

## What went well (Continue)
- _at the retro_

## What didn't go well (Stop)
- _at the retro_

## What to try (Start)
- _at the retro_

## Action items for next sprint (max 3)
| Action | Owner | How we'll know it worked |
|---|---|---|
| _at the retro_ | | |

## Team mood (1–5, anonymous)
Average: _at the retro_ (previous: not recorded)
