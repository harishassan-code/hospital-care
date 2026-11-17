---
description: Write the Operations notes for a shipped bolt and close it out
argument-hint: <bolt id, e.g. B01>
---

Close out bolt **$ARGUMENTS** following AGENTS.md.

1. Confirm its PR(s) are merged into `main` (ask if unsure) and ask the human what they saw on staging.
2. Write `docs/aidlc/operations/<same file name as the spec>` from
   `docs/aidlc/templates/operations-notes-template.md`: what shipped (with PR links), how it was checked on
   staging, anything to watch, and follow-ups. Each follow-up should say whether it becomes a new bolt.
3. In the bolt file, tick the exit checklist and set `status: Done`; run `python3 scripts/aidlc_board.py`.
4. List the issue(s) the human can now close, and any bolt that this unblocks.
