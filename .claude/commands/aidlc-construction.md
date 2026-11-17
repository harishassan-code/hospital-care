---
description: Plan and build an approved bolt unit by unit (AIDLC Construction)
argument-hint: <bolt id, e.g. B01>
---

Run the Construction phase for bolt **$ARGUMENTS** following AGENTS.md.

1. Find the bolt's Inception spec in `docs/aidlc/inception/`. If its Approval line isn't signed, stop and say so.
2. Write `docs/aidlc/construction/<same file name>` from `docs/aidlc/templates/construction-plan-template.md`:
   small units in build order (usually model + service → API → frontend API client + mocks → page), each with
   files touched and tests. Show it and wait for a go-ahead.
3. Build one unit at a time. For each: write the tests with the code, run the checks from AGENTS.md, and commit
   with a message naming the bolt and issue. Stop after each unit with a short summary of what changed.
4. Keep `permissions.py` and `roles.ts` identical, audit-log every state change, and remove the module from
   `frontend/src/features/staff/planned.ts` when its real page lands.
5. When all units are in, tick the acceptance criteria in the spec that are met, and list anything left over.
