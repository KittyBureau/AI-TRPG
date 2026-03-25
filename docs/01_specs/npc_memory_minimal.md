# NPC Memory Minimal (T1)

This document defines the minimal NPC memory integration built on top of the
campaign fact system.

## Scope

- Memory is per-NPC only.
- Memory is stored as fact-system entries.
- Memory is summary-only; raw dialogue logs are out of scope.
- Memory is injected only for the currently selected NPC target.

Non-goals:

- no global memory
- no shared memory across NPCs
- no consequence system inside NPC memory itself
- light narrative consequences now live in the separate T7 `campaign.json.consequences` carrier
- no complex summarization pipeline
- no conflict resolution engine
- no separate memory storage files

## Representation

NPC memory uses the existing fact schema:

```json
{
  "fact_type": "npc_memory",
  "authority": "uncertain",
  "reliability": "generated",
  "scope": {
    "kind": "npc",
    "ref_id": "guide_01"
  },
  "lifecycle": "temporary"
}
```

Rules:

- NPC memory is not authoritative world truth.
- NPC memory is treated as local conversational context only.
- T1 uses temporary lifecycle by default.

## Write Path

- Successful `scene_action talk` turns may write one memory fact for the talked NPC.
- The summary is built from the current turn input through a small heuristic.
- The stored value is a short topic summary, not the raw input log.

## Injection Path

- Injection is gated by the current selected scene target.
- Only when the selected target is an NPC:
  - read `npc_memory` facts for that NPC
  - select up to `3`
  - inject them into `Context.npc_memory`
- Other NPCs do not receive that memory.
- General `Context.fact_context` excludes `scope.kind=npc` to avoid prompt pollution.

## Debug

When trace is enabled, `debug.npc_memory` shows:

- injected items
- selected `fact_ids`
- omitted-by-limit ids
- expired ids
