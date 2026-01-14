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
