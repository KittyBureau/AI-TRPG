# P2 Runtime Context Architecture - Developer Reference

Last updated: 2026-03-10

## Positioning

This document is a developer reference for future P2 implementation and tuning.

- It is not a specification.
- It is not an implementation plan.
- The authoritative implementation-driving board remains `docs/90_playable/PLAYABLE_V1_TODO.md`.
- Use it together with the split `P2-11A` through `P2-11J` task entries rather than as a substitute for the TODO board.
- Use `P2_RUNTIME_CONTEXT_ARCHITECTURE_OVERVIEW.md` for quick flow or authority alignment and `P2_CONTEXT_BUILDER_IMPLEMENTATION_PREP.md` for the first builder coding pass boundary.

## 1. Purpose of P2 Context Architecture

P2 context architecture exists to support long-running TRPG sessions under context window limits without replaying unbounded conversation history every turn.

The key architectural idea is thin projected context instead of full conversation history. The runtime should select a narrow prompt view from authoritative state, recent history, and structured memory while preserving the existing P1 gameplay pipeline and authority model.

## 2. Architectural Core Principles

- Authoritative runtime state remains the single source of truth.
- Context builder output is advisory prompt projection only.
- Structured memory is advisory recall data only.
- The memory update pipeline is deterministic and runs after authoritative turn resolution.
- Fallback recall is a same-turn rescue path only, not the default runtime path.

Memory must never override authoritative runtime state. If runtime state and memory disagree, runtime state wins.

## 3. Structural Components (Expected to Remain Stable)

These are architecture-level elements and should change rarely:

- Runtime authority rooted in campaign state and existing turn execution flow.
- Context builder interface and its before-turn lifecycle position.
- Memory update pipeline lifecycle position after tool execution and state resolution.
- Context assembly order: core state, recent history, structured memory, optional recalled recap.
- Token budget management as a first-class runtime constraint.

These define the architecture shape, not tuning policy.

## 4. Policy Components (Expected to Evolve)

These are expected to change during gameplay tuning:

- Event memory write thresholds.
- State memory update and supersession rules.
- Recall trigger rules.
- Focus layer heuristics.
- Token budget policy and layer caps.
- Memory candidate selection rules.

Most iteration should happen here rather than by changing structural boundaries.

## 5. Known Implementation Risks

- Memory inflation: too many low-value records reduce recall quality and increase selection noise.
- Memory starvation: write thresholds can become so strict that important long-session facts are lost.
- State vs memory inconsistency: advisory memory may become stale if correction and supersession rules are weak.
- Fallback recall overuse: same-turn rescue can become an accidental default path and increase runtime cost.
- Event memory explosion: storing too many events turns recall into transcript replay by another name.
- Context projection misses critical facts: thin prompts can omit needed state or history cues.
- Token spikes during complex scenes: recall recaps, recent history, and dense scene state can combine badly under pressure.

## 6. Expected Iteration Areas

Multiple tuning passes are likely for:

- Event memory thresholds.
- Focus layer heuristics.
- Recall trigger conditions.
- Memory candidate ranking and selection.

This is expected tuning work, not evidence that the architecture is wrong.

## 7. Behavioral Expectations During Early P2

Early P2 should be expected to show:

- Imperfect recall.
- Some missed historical references.
- Conservative responses when facts are unclear or not recalled safely.
- Occasional same-turn fallback recall use for older or ambiguous references.

Early iterations should prioritize correctness, authority consistency, and bounded runtime behavior before optimizing recall richness.

## 8. Practical Testing Scenarios

Recommended manual checks:

- Long-session continuity across many turns without prompt growth drift.
- Old event recall from outside the default recent-history window.
- Ambiguous reference handling with conservative fallback behavior.
- State vs memory consistency when runtime state has changed since older events.
- Token budget stress during dense scenes with recent history, structured memory, and recall recap pressure.

## 9. Long-Term Roadmap Context

The following are intentionally postponed to later P2+ or P3 work:

- Embedding retrieval.
- Semantic ranking or reranking.
- Memory summarization layers.
- Advanced event graph or event-chain modeling.
- Memory aging, archive, and cleanup strategy beyond minimum inactive or superseded handling.

These are future enhancements, not part of the initial P2 runtime context architecture baseline.
