# TODO_CONTEXT

This document tracks the follow-up work for context compression and key-fact
substitution. Read this before implementing or modifying any context pipeline.

## 4.1 Context compression plan (key facts)
- [x] TODO(context): implement compact_context strategy (wire mode switch).
- [x] TODO(context): replace full history with compact key facts per this doc.
- [x] compact_context strategy: keep key facts only (character sheet highlights
      + last N turns + world state summary).
- [ ] Auto-summary trigger: when history exceeds token_budget * X%, generate a
      rolling summary (V1/V2).
- [ ] Key fact extraction: extract people, goals, places, items, quest progress
      into structured JSON.
- [ ] Pin fixed info: key character/rules entries never trimmed.
- [ ] Configurable priority and max length per injection block.
- [ ] Token budget estimation + visibility (log first, UI later).
- [ ] Regression checks: same input under full_context vs compact_context stays
      stable enough for gameplay.
- [ ] Role confusion guard: reinforce GM identity in system prompt and wrap
      character sheet injection to prevent PC self-identification.
- [ ] GM persona lock: prompt rules + input interception + output fallback
      validation (tighten detection and labeling rules).

## 4.2 Acceptance criteria
- V0: full-context works; character injection works; overlong input errors out;
      per-conversation lock blocks concurrent send; conversation file recovers.
- V1: compact_context toggle works; key-fact substitution works; token cost down
      without obvious drift.
