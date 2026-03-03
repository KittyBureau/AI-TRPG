# Storage Layout (Stage 4)

All persistent data is stored under the workspace root:

```
storage/
  worlds/
    world_001/
      world.json
  campaigns/
    camp_0001/
      campaign.json
      turn_log.jsonl
```

## world.json (MVP v1)

World data is stored independently from campaigns. Campaigns keep only
`selected.world_id` as a reference.

```json
{
  "world_id": "world_001",
  "name": "world_001",
  "seed": 123456789,
  "generator": {
    "id": "stub",
    "version": "1",
    "params": {
      "seed_source": "world_id_hash"
    }
  },
  "schema_version": "1",
  "created_at": "2026-03-03T00:00:00+00:00",
  "updated_at": "2026-03-03T00:00:00+00:00"
}
```

World lazy-create migration (v1):

- `GET /api/v1/campaigns/{campaign_id}/world` reads `campaign.selected.world_id`.
- If `world_id` is empty/missing, API returns `409 Conflict`.
- If `world.json` is missing, backend lazily creates a deterministic stub
  world under `storage/worlds/{world_id}/world.json` and returns `200`.
- If `campaign_id` is missing, API returns `404 Not Found`.

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
  "allowlist": ["move", "move_options", "hp_delta", "map_generate", "world_generate"],
  "map": {
    "areas": {
      "area_001": {
        "id": "area_001",
        "name": "Starting Area",
        "parent_area_id": null,
        "reachable_area_ids": ["area_002"]
      },
      "area_002": {
        "id": "area_002",
        "name": "Side Room",
        "parent_area_id": null,
        "reachable_area_ids": []
      }
    },
    "connections": [
      { "from_area_id": "area_001", "to_area_id": "area_002" }
    ]
  },
  "state": {
    "positions": {},
    "positions_parent": {},
    "positions_child": {}
  },
  "actors": {
    "pc_001": {
      "position": "area_001",
      "hp": 10,
      "character_state": "alive",
      "meta": {}
    },
    "pc_002": {
      "position": "area_001",
      "hp": 10,
      "character_state": "alive",
      "meta": {}
    }
  },
  "positions": {},
  "hp": {},
  "character_states": {},
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
      "auto_type_enabled": true,
      "strict_semantic_guard": false,
      "conflict_text_checks_enabled": false,
      "turn_profile_trace_enabled": false
    },
    "characters": {
      "fact_generation": {
        "draft_mode": "deterministic"
      }
    }
  },
  "goal": {
    "text": "Define the main objective",
    "status": "active"
  },
  "milestone": {
    "current": "intro",
    "last_advanced_turn": 0,
    "turn_trigger_interval": 6,
    "pressure": 0,
    "pressure_threshold": 2,
    "summary": ""
  },
  "lifecycle": {
    "ended": false,
    "reason": null,
    "ended_at": null
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
| map | object | Areas and derived connections. |
| map.areas.*.reachable_area_ids | array | Authoritative outbound reachability list. |
| map.connections | array | Derived from `reachable_area_ids` on write. |
| state | object | Reserved for future map-related flags; not authoritative for actor positions. |
| state.positions | object | Legacy position mirrors (empty after migration). |
| state.positions_parent | object | Legacy position mirrors (empty after migration). |
| state.positions_child | object | Legacy position mirrors (empty after migration). |
| actors | object | Actor state keyed by actor id (`position` is authoritative). |
| positions | object | Legacy positions (empty after migration; derived from actors when needed). |
| hp | object | Legacy HP map (empty after migration; derived from actors when needed). |
| character_states | object | Legacy character state map (empty after migration; derived from actors when needed). |
| settings_snapshot | object | Current settings snapshot. |
| settings_snapshot.context | object | Context settings. |
| settings_snapshot.rules | object | Rules settings. |
| settings_snapshot.rollback | object | Rollback settings (stage 2 only stores). |
| settings_snapshot.dialog | object | Dialog settings. |
| settings_snapshot.characters | object | Character generation settings. |
| goal | object | Goal placeholder. |
| milestone | object | Milestone progression state and lightweight pressure counters. |
| lifecycle | object | Campaign lifecycle status (`ended`, `reason`, `ended_at`). |
| created_at | string | ISO timestamp. |

## Character access boundary (current)

- `backend/domain/character_access.py` provides the supported access path for
  character runtime fields.
- Runtime authority remains `actors.*` values in `campaign.json`.
- `positions`, `hp`, and `character_states` remain compatibility mirrors and
  should not be accessed directly in turn/tool critical paths.
- Future fact/state file split is planned behind the same facade:
  - `storage/characters_library/{id}.json`
  - `storage/campaigns/{campaign_id}/characters/{id}.fact.json`
  - `storage/campaigns/{campaign_id}/characters/{id}.state.json`

## CharacterFact generated artifacts (temporary, non-authoritative)

Generated CharacterFact outputs are stored for review/reuse and do not replace
runtime actor authority:

- `storage/campaigns/{campaign_id}/characters/generated/batch_{utc_ts}_{request_id}.json`
- `storage/campaigns/{campaign_id}/characters/generated/{character_id}.fact.draft.json`
- `storage/campaigns/{campaign_id}/characters/generated/{character_id}.fact.accepted.json`

Batch payload shape:

```json
{
  "schema_id": "character_fact.v1",
  "schema_version": "1",
  "campaign_id": "camp_0001",
  "request_id": "req_001",
  "utc_ts": "20260210T153000Z",
  "params": {},
  "items": []
}
```

Individual draft payload shape:

```json
{
  "character_id": "ch_a1b2c3d4",
  "name": "Name",
  "role": "scout",
  "tags": [],
  "attributes": {},
  "background": "",
  "appearance": "",
  "personality_tags": [],
  "meta": {
    "hooks": [],
    "language": "zh-CN",
    "source": "llm"
  }
}
```

Rules:

- Runtime fields (`position`, `hp`, `character_state`) are forbidden in facts.
- `meta` is predefined-only (`hooks`, `language`, `source`).
- `request_id` must be unique within one campaign (`409 Conflict` on duplicate submit).
- `__AUTO_ID__` is never written to disk; IDs are allocated before batch/individual writes.
- Adoption status is sidecar-based and does not mutate CharacterFact schema:
  - sidecar keys: `character_id`, `accepted_at`, `accepted_by`, `source_draft_ref`.
- Turn/tool request-response contracts remain unchanged.

Behavior source-of-truth note:

- File format/path guarantees are defined here.
- API behavior guarantees (including GET fact fallback and generate error precedence)
  are test-backed in `docs/01_specs/character_fact_v1.md` section 8.

## Map normalization and validation

- `map.areas.*.reachable_area_ids` is the authoritative adjacency list.
- `map.connections` is derived from `reachable_area_ids` and normalized on write.
- Validation rules (enforced in `backend/domain/map_models.py`):
  - Reachable ids are strings only.
  - No duplicate reachable ids per area.
  - No self-loop (`area_id` cannot reach itself).
  - All reachable ids must exist in `map.areas`.
  - For each `parent_area_id` group with more than one area, the graph must be connected.

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
      "args": { "actor_id": "pc_001", "to_area_id": "area_002" },
      "result": { "from_area_id": "area_001", "to_area_id": "area_002" },
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
    "positions_parent": {
      "pc_001": "area_002",
      "pc_002": "area_001"
    },
    "positions_child": {
      "pc_001": null,
      "pc_002": null
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

Breaking change: move tool_calls no longer accept `from_area_id` in args. Any tool_call
that includes `from_area_id` now fails with `invalid_args`. The backend still records
`from_area_id` in applied_actions for audit.
`actor_id` may be omitted in move args and then defaults to `selected.active_actor_id`.
`to_area_id` must exist and be reachable from the actor's current area; same-area move is rejected.
When repeat-illegal-request suppression is triggered (same failed tool+args over the recent 3 turns),
tool feedback may include reason `repeat_illegal_request`.

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
| state_summary | object | Includes `active_actor_id`, `positions`, `positions_parent`, `positions_child`, `hp`, `character_states` (derived from `actors`). |
