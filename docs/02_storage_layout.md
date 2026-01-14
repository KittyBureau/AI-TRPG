# Storage Layout (Stage 4)

All persistent data is stored under the workspace root:

```
storage/
  campaigns/
    camp_0001/
      campaign.json
      turn_log.jsonl
```

## campaign.json (minimal)

```json
{
  "id": "camp_0001",
  "selected": {
    "world_id": "world_001",
    "map_id": "map_001",
    "party_character_ids": ["pc_001", "pc_002"],
    "active_actor_id": "pc_001"
  },
  "settings_revision": 0,
  "allowlist": ["move", "hp_delta", "map_generate"],
  "map": {
    "areas": {
      "area_001": { "id": "area_001", "name": "Starting Area", "parent_area_id": null },
      "area_002": { "id": "area_002", "name": "Side Room", "parent_area_id": null }
    },
    "connections": [
      { "from_area_id": "area_001", "to_area_id": "area_002" }
    ]
  },
  "positions": {
    "pc_001": "area_001",
    "pc_002": "area_001"
  },
  "hp": {
    "pc_001": 10,
    "pc_002": 10
  },
  "character_states": {
    "pc_001": "alive",
    "pc_002": "alive"
  },
  "settings_snapshot": {
    "context": {
      "full_context_enabled": true,
      "compress_enabled": false
    },
    "rules": {
      "hp_zero_ends_game": true
    },
    "rollback": {
      "max_checkpoints": 0
    },
    "dialog": {
      "auto_type_enabled": true
    }
  },
  "goal": {
    "text": "Define the main objective",
    "status": "active"
  },
  "milestone": {
    "current": "intro",
    "last_advanced_turn": 0
  },
  "created_at": "2026-01-14T16:05:00+00:00"
}
```

## campaign.json fields

| Field | Type | Notes |
| --- | --- | --- |
| id | string | Campaign id. |
| selected | object | World/map/party selection. |
| settings_revision | int | Settings revision, increments on valid patch. |
| allowlist | array | Allowed tools for this campaign. |
| map | object | Areas and connections. |
| positions | object | Character positions by id. |
| hp | object | Character HP by id. |
| character_states | object | Character state by id. |
| settings_snapshot | object | Current settings snapshot. |
| settings_snapshot.context | object | Context settings. |
| settings_snapshot.rules | object | Rules settings. |
| settings_snapshot.rollback | object | Rollback settings (stage 2 only stores). |
| settings_snapshot.dialog | object | Dialog settings. |
| goal | object | Goal placeholder. |
| milestone | object | Milestone placeholder. |
| created_at | string | ISO timestamp. |

## turn_log.jsonl (append-only)

Each line is a JSON object:

```json
{
  "turn_id": "turn_0001",
  "timestamp": "2026-01-14T16:05:30+00:00",
  "user_input": "I light a torch.",
  "dialog_type": "scene_description",
  "dialog_type_source": "model",
  "settings_revision": 0,
  "assistant_text": "Echo: I light a torch.",
  "assistant_structured": {
    "tool_calls": [
      { "id": "call_001", "tool": "move", "args": {}, "reason": "demo" }
    ]
  },
  "applied_actions": [
    {
      "tool": "move",
      "args": { "actor_id": "pc_001", "from_area_id": "area_001", "to_area_id": "area_002" },
      "result": { "to_area_id": "area_002" },
      "timestamp": "2026-01-14T16:05:31+00:00"
    }
  ],
  "tool_feedback": {
    "failed_calls": [
      {
        "id": "call_002",
        "tool": "hp_delta",
        "status": "rejected",
        "reason": "actor_state_restricted"
      }
    ]
  },
  "conflict_report": {
    "retries": 1,
    "conflicts": [
      {
        "type": "state_mismatch",
        "field": "hp.pc_001",
        "expected": 0,
        "found_in_text": "still healthy"
      }
    ]
  },
  "state_summary": {
    "active_actor_id": "pc_001",
    "positions": {
      "pc_001": "area_002",
      "pc_002": "area_001"
    },
    "hp": {
      "pc_001": 10,
      "pc_002": 10
    },
    "character_states": {
      "pc_001": "alive",
      "pc_002": "alive"
    }
  }
}
```

## turn_log.jsonl fields

| Field | Type | Notes |
| --- | --- | --- |
| turn_id | string | Turn id. |
| timestamp | string | ISO timestamp. |
| user_input | string | Raw player input. |
| dialog_type | string | Classified dialog type. |
| dialog_type_source | string | `model` or `fallback`. |
| settings_revision | int | Settings revision at this turn. |
| assistant_text | string | LLM output. |
| assistant_structured | object | Tool calls container. |
| applied_actions | array | Applied tool results. |
| tool_feedback | object | Failed tool calls with reasons. |
| conflict_report | object | Conflict info when retries occur. |
| state_summary | object | Includes `active_actor_id`, `positions`, `hp`, `character_states`. |
