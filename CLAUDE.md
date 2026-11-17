@AGENTS.md

## Claude Code

Slash commands for the AIDLC workflow live in `.claude/commands/`:

| Command | What it does |
|---|---|
| `/bolt-start B01` | Reads the bolt, claims it for you, and drafts its Inception spec. Stops for approval. |
| `/aidlc-construction B01` | After the spec is approved: writes the construction plan, then builds it unit by unit. |
| `/aidlc-operations B01` | After it's live on staging: writes the operations notes and closes out the bolt. |
| `/bolt-board` | Regenerates and summarises the bolt board: what's ready, blocked, in progress. |
