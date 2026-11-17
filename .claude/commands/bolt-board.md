---
description: Regenerate the AIDLC bolt board and summarise what can be picked up
---

1. Run `python3 scripts/aidlc_board.py` and fix any error it reports in the bolt files.
2. Read `docs/aidlc/bolts/README.md` and summarise: bolts in progress (and who owns them), bolts **ready to start**
   (all `depends_on` Done, no owner), and bolts blocked (and by what). Flag anyone holding more than 2 in progress.
3. For a bolt in `Backlog` whose dependencies are now all Done, suggest moving it to `Ready`.
