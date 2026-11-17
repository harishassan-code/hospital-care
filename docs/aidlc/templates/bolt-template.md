---
id: BNN
title: <short imperative title>
issues: <issue numbers, comma separated>
points: <story points, Fibonacci>
priority: <highest | high | medium | low>
sprint: <target sprint number, or stretch>
depends_on: <bolt ids, comma separated, or ->
owner: unassigned
status: Backlog
---

# BNN · <title>

**Goal:** <one or two sentences: what is true when this bolt is done, and who it is for.>

## Stories and acceptance criteria

<Copied from the linked issue(s). The Inception spec may refine these, never silently drop them.>

## Build on

<Existing code, endpoints, models and patterns the owner should reuse, with paths. This is what keeps a bolt
short: nobody starts from a blank page.>

## Scope

- **In:** <…>
- **Out:** <… (and which bolt or issue covers it instead)>

## Open questions for Inception

<Decisions the spec must settle and the Product Owner / Scrum Master must approve before code is written.>

## Exit checklist

- [ ] Inception spec `docs/aidlc/inception/<date>-<slug>.md` approved (sign-off line filled in)
- [ ] Construction plan `docs/aidlc/construction/<date>-<slug>.md` written
- [ ] Code, tests and docs merged; CI green; Definition of Done met
- [ ] Operations notes `docs/aidlc/operations/<date>-<slug>.md` written after it's live on staging
- [ ] `status: Done` here, board regenerated, issue(s) closed
