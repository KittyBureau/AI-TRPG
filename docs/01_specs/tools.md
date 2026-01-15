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
    "from_area_id": "area_001",
    "to_area_id": "area_002"
  },
  "reason": "Move to the next room"
}
```

## Allowed Tools (default allowlist)

- `move`
- `hp_delta`
- `map_generate`

Allowlist is stored in `campaign.json` as `allowlist`.

## Tool Parameters

### move

Required args:

- `actor_id`
- `from_area_id`
- `to_area_id`

Notes:

- `actor_id` must match the active actor for the turn.

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
    "from_area_id": "area_001",
    "to_area_id": "area_002"
  },
  "result": { "to_area_id": "area_002" },
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
