# Generated Fact Foundation (T4 / T5)

This document defines the minimal campaign-level fact foundation and the first
control layer on top of it.

## Scope

- T4: facts can exist in a unified campaign-level container.
- T5: facts stay bounded, scoped, and prompt-safe.

Non-goals:

- no NPC memory system
- no consequence engine inside the fact system itself
- light narrative consequences now live in the separate T7 `campaign.json.consequences` carrier
- no free-action fact extraction
- no automatic conflict merge workflow
- no multi-file fact storage layout
- no ranking/scoring system beyond simple deterministic rules

## Runtime Authority

Facts are split by trust level:

- `authority=authoritative`
  - safe to treat as established campaign truth
- `authority=uncertain`
  - generated / reported / tentative information

`reliability` is a second lightweight signal:

- `confirmed`
- `reported`
- `generated`

Facts do not replace runtime authority such as:

- `campaign.actors`
- `campaign.items`
- `campaign.entities`
- `campaign.map`

## Schema

Campaign facts use the following unified shape:

```json
{
  "fact_id": "fact_abc123def456",
  "fact_type": "route_hint",
  "summary": "A service passage may bypass the main archive door.",
  "content": "",
  "source": {
    "kind": "llm",
    "ref_id": "turn_0007",
    "actor_id": "pc_001"
  },
  "authority": "uncertain",
  "reliability": "generated",
  "scope": {
    "kind": "area",
    "ref_id": "returns_annex"
  },
  "lifecycle": "temporary",
  "expires_turn_index": 12,
  "created_turn_index": 7,
  "metadata": {}
}
```

Field notes:

- `fact_id`: stable storage id
- `fact_type`: small category label for future selection/conflict checks
- `summary`: required short statement
- `content`: optional longer detail
- `source`: origin descriptor (`manual|llm|tool|system|import`)
- `authority`: `authoritative|uncertain`
- `reliability`: `confirmed|reported|generated`
- `scope.kind`: primary T5 kinds are `campaign|area|npc|entity`
- compatibility scope kinds retained for current runtime seams: `actor|item`
- `scope.ref_id`: required for non-campaign scopes
- `lifecycle`: `persistent|temporary`
- `expires_turn_index`: optional explicit expiry for temporary facts
- `created_turn_index`: turn-local time anchor; `0` is allowed for pre-turn/manual insert
- `metadata`: additive bag for future narrow extensions

## Storage

Facts are stored in `storage/campaigns/{campaign_id}/campaign.json` under the
top-level `facts` container.

Rules:

- `facts` is campaign-level only.
- Missing `facts` on old campaigns is valid and normalizes to `{}`.
- The storage layout remains single-file; there is no separate `facts/` directory.

## Read / Write Boundary

Service boundary:

- `backend/app/campaign_fact_service.py`
  - `add_fact(campaign_id, payload)`
  - `get_fact(campaign_id, fact_id)`
  - `list_facts(campaign_id, ...)`

Persistence boundary:

- facts are saved only through normal campaign persistence (`FileRepo.save_campaign`)
- T5 pruning mutates the same `campaign.json` container; it does not introduce a parallel store

## Prompt Injection Boundary

Prompt injection is reserved through `Context.fact_context`.

Current behavior:

- `turn_service` builds a compact fact context block before prompt render
- the block is additive only
- no current tool contract depends on facts
- no `state_summary` contract change is introduced

`Context.fact_context` shape:

```json
{
  "slot": "campaign_facts_v1",
  "authoritative": [],
  "uncertain": []
}
```

T5 control rules:

- prompt facts are selected through a hard-capped selector
- default max injection count is `5`
- temporary expired facts are excluded before ranking
- authoritative facts rank above uncertain facts
- current-area facts rank above other-area facts
- more recent facts rank above older facts when earlier rules tie
- `scope.kind=npc` facts are excluded from general `fact_context` and use the dedicated
  local `Context.npc_memory` path instead

Trace/debug may include a richer `debug.fact_context` block with:

- selection metadata
- selected ids
- expired temporary ids
- suppressed uncertain ids
- omitted-by-limit ids
- active policy values

## Lifecycle

- `persistent`
  - remains eligible for prompt ranking unless excluded by scope/limit
- `temporary`
  - may expire through explicit `expires_turn_index`
  - when no explicit expiry is provided, a small default TTL is applied

T5 does not add archive, merge, downgrade, or promotion workflows.

NPC memory note:

- minimal per-NPC memory is layered on top of this system through `fact_type=npc_memory`
- see `docs/01_specs/npc_memory_minimal.md`

## Pruning

Pruning stays intentionally weak:

- expired temporary facts are removed first
- when stored fact count exceeds the soft limit, remove temporary facts only
- removal priority prefers:
  - uncertain temporary facts
  - lower-reliability temporary facts
  - older temporary facts

Persistent facts are not auto-deleted by T5 pruning.

## Minimal Conflict Strategy

T4/T5 conflict handling remains intentionally small:

- same-source exact duplicates are deduped on write
- conflicting facts are not auto-merged
- authoritative facts take precedence at prompt-selection time
- when an authoritative fact and an uncertain fact share the same
  `(fact_type, scope.kind, scope.ref_id)`, the uncertain fact is suppressed from
  prompt injection
- storage may still retain both facts for later review/lifecycle work

This is a guardrail, not a full resolution engine.
