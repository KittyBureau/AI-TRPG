# Tools (Stage 3)

Stage 3 introduces tool requests and system-side execution decisions.

## Tool Calls (AI -> System)

Structure:

```json
{
  "id": "call_001",
  "tool": "move",
  "args": {
    "actor_id": "pc_001",
    "to_area_id": "area_002"
  },
  "reason": "Move to the next room"
}
```

Breaking change: `move` tool_call args no longer accept `from_area_id`. Any `from_area_id`
included in tool_calls now results in `invalid_args`.

## Tool-call movement: prompt contract (anti-silent response)

Contract:

- Output schema: `assistant_text`, `dialog_type`, `tool_calls`.
- Movement intent -> tool_calls must include `move`; assistant_text may be empty or a very short plan_note.
- If narration implies item gain (obtain/loot/pick up/receive), tool_calls must include `inventory_add`.
- If narration implies injury/heal/HP change, tool_calls must include `hp_delta`.
- Target unclear or user asks where they can go -> use `move_options`; explicitly state no movement yet.
- If tool_calls is empty -> assistant_text MUST be a non-empty GM response; must not claim completed movement.
- Context JSON uses `ensure_ascii=False` so Chinese remains readable in the prompt.

Examples (schema-accurate):

Example 1 (move intent is explicit and IDs are known; assistant_text empty; actor_id/to_area_id
must come from Context.effective_actor_id and the user's target; from_area_id is derived by the backend):

```json
{"assistant_text":"","dialog_type":"scene_description","tool_calls":[{"id":"call_move_1","tool":"move","args":{"actor_id":"pc_001","to_area_id":"area_002"}}]}
```

Example 2 (target unclear or user asks where they can go; use move_options; no movement yet; actor_id should
come from Context.effective_actor_id):

```json
{"assistant_text":"No movement yet. I will fetch 1-hop options.","dialog_type":"scene_description","tool_calls":[{"id":"call_move_options_1","tool":"move_options","args":{"actor_id":"pc_001"}}]}
```

Example 3 (no tool call required; MUST respond with non-empty assistant_text):

```json
{"assistant_text":"You are currently in area_002. The corridor is quiet. What do you do next?","dialog_type":"scene_description","tool_calls":[]}
```

## Allowed Tools (default allowlist)

- `move`
- `move_options`
- `hp_delta`
- `inventory_add`
- `map_generate`
- `world_generate`
- `actor_spawn`
- `scene_action`

Allowlist is stored in `campaign.json` as `allowlist`.

## Turn Execution Actor Context

- `POST /api/v1/chat/turn` accepts execution context via `execution.actor_id`.
- Compatibility mode: top-level `actor_id` is still accepted.
- Effective execution actor resolution:
  1. `execution.actor_id`
  2. top-level `actor_id`
  3. `campaign.selected.active_actor_id`
- Tool permission checks and actor-bound tool execution use this effective actor id.
- If a tool call provides `args.actor_id`, it must exactly match the resolved effective actor id for that turn.
  - mismatch is rejected with `reason=actor_context_mismatch`
  - empty/non-string `actor_id` is rejected with `reason=invalid_args`
- `selected.active_actor_id` remains UI/session focus, not the hard authority for every turn.
- Turn execution is serialized per campaign. Concurrent turns on the same campaign return `409 Conflict`.

## Tool Parameters

### move

Required args:

- `to_area_id`

Optional args:

- `actor_id` (defaults to effective actor id for this turn)

Notes:

- If provided, `actor_id` must match the effective actor for the turn.
- `from_area_id` is derived by the backend from the actor's current position and MUST NOT be provided.
- `to_area_id` must exist in `map.areas` and be 1-hop reachable from the actor's current area.
- If `to_area_id` equals the current area, the call is rejected as `invalid_args`.
- Movement occurs only when a `move` tool_call is executed; narration alone does not move characters.

### move_options

Required args:

- none

Optional args:

- `actor_id` (defaults to effective actor id for this turn)

Notes:

- Read-only tool; does not change actor positions or other state.
- Returns 1-hop reachable neighbors from the actor's current area.
- If provided, `actor_id` must match the effective actor for the turn.
- Use for questions like "Can I move?" or "Where can I go?" without committing to movement.

### hp_delta

Required args:

- `target_character_id`
- `delta`
- `cause`

### inventory_add

Required args:

- `item_id`

Optional args:

- `quantity` (int, default `1`, must be `> 0`)
- `actor_id` (defaults to effective actor id for this turn; if provided must match it)

Notes:

- Adds quantity to `actors[actor_id].inventory[item_id]`.
- `item_id` must be a non-empty string.
- Invalid item/quantity/actor args fail with `reason=invalid_args`.

### map_generate

Required args:

- `parent_area_id`
- `theme` or `constraints` (optional payload)

Optional constraints:

- `size` (int, default 6, range 1..30)
- `seed` (string, deterministic variation)

Notes:

- `parent_area_id` may be null to generate a root layer.
- `map.connections` are rebuilt from `areas[*].reachable_area_ids` on write.

### world_generate

Required args:

- none

Optional args:

- `world_id` (string; resolution order: args.world_id -> Context.selected.world_id)
- `bind_to_campaign` (bool, default `false`)
- `seed` (int|string; only used when creating world or when seed is missing)
- `generator_id` (string; only used as a fallback when generator id is missing)
- `also_generate_map` (bool, default `false`; v1 echoes only, no map generation)

Notes:

- v1 does not call `map_generate`.
- If resolved world id is missing, the tool fails with `reason=world_id_missing`.
- If world exists, only missing/empty fields are normalized; existing values are not overwritten.
- `bind_to_campaign=true` updates `campaign.selected.world_id`; default `false` keeps selection unchanged.

### actor_spawn

Required args:

- `character_id` (string; stored into `actors[actor_id].meta.character_id`)

Optional args:

- `spawn_position` (string; must exist in `map.areas` when provided)
- `bind_to_party` (bool, default `true`)

Spawn position priority:

- `args.spawn_position`
- active actor current position
- `area_001`

Notes:

- Runtime actor id is generated by backend (`actor_{uuid}`) and is independent from `character_id`.
- Invalid explicit `spawn_position` fails with `reason=invalid_args` (no silent fallback).
- `bind_to_party=true` appends new actor id to `selected.party_character_ids`.
- `bind_to_party=false` keeps `selected.party_character_ids` unchanged.
- If `selected.active_actor_id` is empty, the spawned actor becomes the active actor.
- Initial state is fixed in MVP: `hp=10`, `character_state=alive`.

### scene_action

Required args:

- `action` (one of: `inspect`, `talk`, `open`, `search`, `take`, `drop`, `detach`, `use`, `wait`)

Optional args:

- `actor_id` (defaults to effective actor id for this turn; if provided must match it)
- `target_id` (required for all current actions except `wait`; `search` can target current area id)
- `params` (object, default `{}`)

Notes:

- This is the single interaction tool for non-move scene actions.
- `move` remains a separate tool.
- Reachability is required: target must resolve to current area or actor inventory chain.
- Verb checks use `entity.verbs` with fallbacks:
  - `inspect` is allowed by default unless explicitly blocked.
  - `talk` is allowed for `kind=npc` or when `talk` verb exists.
- Weak carry rule applies to `take` / `detach`:
  - total carried mass cannot exceed actor carry limit (default `60`).
  - overflow returns `ok=false` with `error.code=carry_limit`.
- Result payload:
  - `ok` (bool)
  - `narrative` (string)
  - `patches.entity_patches[]`
  - `patches.new_entities[]`
  - `patches.removed_entities[]`
  - `error` (`{code,message}` when `ok=false`)

## Applied Actions (System -> Log)

```json
{
  "tool": "move",
  "args": {
    "actor_id": "pc_001",
    "to_area_id": "area_002"
  },
  "result": { "from_area_id": "area_001", "to_area_id": "area_002" },
  "timestamp": "2026-01-14T16:05:31+00:00"
}
```

Map generation result payload:

```json
{
  "tool": "map_generate",
  "args": {
    "parent_area_id": "area_001",
    "theme": "Cave",
    "constraints": { "size": 6, "seed": "alpha" }
  },
  "result": {
    "created_area_ids": ["area_003", "area_004"],
    "created_connections": 3,
    "root_parent_area_id": "area_001",
    "warnings": []
  },
  "timestamp": "2026-01-14T16:05:31+00:00"
}
```

World generation result payload (v1):

```json
{
  "tool": "world_generate",
  "args": {
    "world_id": "world_001",
    "bind_to_campaign": true,
    "also_generate_map": false
  },
  "result": {
    "world_id": "world_001",
    "created": false,
    "normalized": true,
    "bound_to_campaign": true,
    "seed": 123456789,
    "generator_id": "stub",
    "also_generate_map": false
  },
  "timestamp": "2026-01-14T16:05:31+00:00"
}
```

Move options result payload:

```json
{
  "tool": "move_options",
  "args": {
    "actor_id": "pc_001"
  },
  "result": {
    "options": [
      { "to_area_id": "area_002", "name": "Side Room" }
    ]
  },
  "timestamp": "2026-01-14T16:05:31+00:00"
}
```

## Tool Feedback (Failures)

```json
{
  "failed_calls": [
    {
      "id": "call_002",
      "tool": "hp_delta",
      "status": "rejected",
      "reason": "actor_state_restricted"
    }
  ]
}
```

### Status

- `rejected`: blocked by allowlist or state rules.
- `error`: invalid or incomplete args.

### Failure Reasons (non-exhaustive)

- `tool_not_allowed`
- `invalid_args`
- `actor_state_restricted`
- `invalid_actor_state`
- `world_id_missing`
- `actor_context_mismatch`
- `not_reachable` (`scene_action` logical failure; returned in `result.error.code`)
- `not_allowed` (`scene_action` logical failure; returned in `result.error.code`)
- `locked` (`scene_action` logical failure; returned in `result.error.code`)
- `carry_limit` (`scene_action` logical failure; returned in `result.error.code`)
- `missing_item` (`scene_action` logical failure; returned in `result.error.code`)
