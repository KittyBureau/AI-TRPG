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
- Target unclear or user asks where they can go -> use `move_options`; explicitly state no movement yet.
- If tool_calls is empty -> assistant_text MUST be a non-empty GM response; must not claim completed movement.
- Context JSON uses `ensure_ascii=False` so Chinese remains readable in the prompt.

Examples (schema-accurate):

Example 1 (move intent is explicit and IDs are known; assistant_text empty; actor_id/to_area_id
must come from Context.selected.active_actor_id and the user's target; from_area_id is derived by the backend):

```json
{"assistant_text":"","dialog_type":"scene_description","tool_calls":[{"id":"call_move_1","tool":"move","args":{"actor_id":"pc_001","to_area_id":"area_002"}}]}
```

Example 2 (target unclear or user asks where they can go; use move_options; no movement yet; actor_id should
come from Context.selected.active_actor_id):

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
- `map_generate`

Allowlist is stored in `campaign.json` as `allowlist`.

## Tool Parameters

### move

Required args:

- `actor_id`
- `to_area_id`

Notes:

- `actor_id` must match the active actor for the turn.
- `from_area_id` is derived by the backend from the actor's current position and MUST NOT be provided.
- Movement occurs only when a `move` tool_call is executed; narration alone does not move characters.

### move_options

Required args:

- none

Optional args:

- `actor_id` (defaults to active actor id)

Notes:

- Read-only tool; does not change actor positions or other state.
- Returns 1-hop reachable neighbors from the actor's current area.
- Use for questions like "Can I move?" or "Where can I go?" without committing to movement.

### hp_delta

Required args:

- `target_character_id`
- `delta`
- `cause`

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
