# P2 Context Builder Implementation Prep

Last updated: 2026-03-10

## Positioning

This note prepares the first Context Builder coding pass without locking in unnecessary internals.

- It is documentation only.
- It does not authorize runtime implementation changes by itself.
- Use it with `PLAYABLE_V1_TODO.md`, `P2_RUNTIME_CONTEXT_DEVELOPER_REFERENCE.md`, and `P2_RUNTIME_CONTEXT_ARCHITECTURE_OVERVIEW.md`.

## 1. Scope of the First Context Builder Implementation

The first Context Builder implementation should be:

- a before-turn runtime layer only
- attached before `_build_system_prompt()`
- projection-only

It must not:

- mutate authoritative runtime state
- own storage authority
- initiate fallback recall by itself
- create an alternate turn execution path

## 2. Required Builder Inputs

The first builder pass should assume these inputs:

- authoritative runtime state
- active actor or selected actor context
- current request context
- recent history slice
- selected structured memory records
- optional recalled recap provided externally

The builder reads these inputs and projects them; it does not decide authority.

## 3. Required Builder Outputs

The builder should output:

- prompt-ready projected context only
- deterministic layer ordering
- deterministic truncation or degradation policy hooks

The output is advisory prompt projection, not a new execution contract.

## 4. Explicit Non-goals for the First Implementation

- no planner role
- no state ownership
- no direct memory writes
- no autonomous retrieval orchestration
- no semantic retrieval

Also excluded from initial P2:

- embeddings
- heavy semantic retrieval
- free-form long-term summarization
- background maintenance requirements

## 5. Open Questions / Later Tuning Areas

These should remain open for later tuning rather than being over-fixed in the first coding pass:

- exact budget numbers
- exact focus heuristics
- exact event selection rules
- exact recall trigger thresholds

The first implementation should prioritize stable boundaries, deterministic behavior, and compatibility with the existing P1 authority chain.
