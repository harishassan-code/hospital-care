---
description: Start an AIDLC bolt and draft its Inception spec (stops for approval)
argument-hint: <bolt id, e.g. B01> [your GitHub handle]
---

Start bolt **$ARGUMENTS** following the AIDLC rules in AGENTS.md.

1. Open `docs/aidlc/bolts/` and read the file whose name starts with the bolt id. Read every file listed
   under its **Build on** section, and the linked GitHub issues if you can reach them.
2. Check its `depends_on` bolts. If any is not `status: Done`, say which ones and what part (if any) can safely go
   ahead, then ask whether to continue.
3. In the bolt file, set `owner:` to the handle given (ask if none was given) and `status: In Progress`, then run
   `python3 scripts/aidlc_board.py`.
4. Draft the Inception spec at `docs/aidlc/inception/<today>-<slug from the bolt file name>.md` from
   `docs/aidlc/templates/inception-spec-template.md`:
   - problem and roles; user stories and acceptance criteria from the bolt (refine them, never drop one);
   - a short **Design** section naming the models, endpoints, permissions and pages, reusing the code in **Build on**;
   - each of the bolt's **Open questions** with a recommended answer marked *proposed*;
   - leave the **Approval** line unsigned.
5. Stop. Summarise the spec and the decisions that need a human answer. **Do not write code** until the human
   says the spec is approved and fills in the Approval line.
