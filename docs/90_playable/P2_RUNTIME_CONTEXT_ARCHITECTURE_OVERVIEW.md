# P2 Runtime Context Architecture Overview

Last updated: 2026-03-10

## Purpose

This document gives a compact runtime-flow and authority-boundary view for P2 implementation work.

- It is not a specification.
- It is not an implementation plan.
- Use it with `PLAYABLE_V1_TODO.md` and `P2_RUNTIME_CONTEXT_DEVELOPER_REFERENCE.md`.

## Main Runtime Flow

```text
authoritative runtime state
  -> context builder
  -> prompt projection
  -> LLM
  -> tool execution
  -> authoritative state update
  -> memory update pipeline
  -> structured memory
```

Notes:

- The builder reads authoritative inputs but does not own state.
- Prompt projection is a thin view, not a second source of truth.
- Memory update happens after authoritative turn resolution.

## Fallback Recall Side Path

```text
unresolved reference
  -> recall trigger
  -> candidate selection
  -> recalled recap
  -> context rebuild
  -> resumed or retried turn handling
```

Notes:

- This is a same-turn rescue path only.
- It is not the default per-turn runtime path.
- Candidate selection remains rule-driven in initial P2.

## Authority Boundary

- Authoritative runtime state is the single source of truth.
- Structured memory is advisory recall data only.
- Context builder is projection-only and must not become a planner or state owner.
- Fallback recall is not normal turn flow and must not become default double-LLM behavior.
- Initial P2 memory writing remains deterministic and rule-driven.

If runtime state and memory disagree, runtime state wins.

## Token Budget Layers

Prompt projection should be assembled in this order:

1. core runtime state
2. request or actor context
3. recent history
4. structured memory
5. optional recall recap

Deterministic degradation order:

1. trim optional recall recap first
2. trim structured memory projection next
3. trim recent history next
4. preserve required request or actor context
5. preserve required core runtime state last

The exact budget numbers are a tuning concern, but the authority-first degradation rule should remain stable.

## Why This Avoids Unbounded History Growth

The runtime does not rely on replaying full conversation history forever. Instead, it projects a narrow prompt view from stable authority, bounded recent history, and selective structured memory. This keeps prompt size controllable while preserving long-session continuity through targeted recall rather than transcript accumulation.
