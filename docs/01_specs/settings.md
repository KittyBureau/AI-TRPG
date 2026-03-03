# Settings (Stage 2)

Stage 2 introduces a registry-driven settings system with validation and audited
patching.

## Definitions

Each setting definition includes:

- `key`
- `type`
- `default`
- `scope`
- `validation`
- `ui_hint`
- `effect_tags`

Registry keys (default values):

- `context.full_context_enabled` (bool, default `true`)
- `context.compress_enabled` (bool, default `false`)
- `rules.hp_zero_ends_game` (bool, default `true`)
- `rollback.max_checkpoints` (int, default `0`)
- `dialog.auto_type_enabled` (bool, default `true`)
- `dialog.strict_semantic_guard` (bool, default `false`)
- `dialog.conflict_text_checks_enabled` (bool, default `false`)
- `dialog.turn_profile_trace_enabled` (bool, default `false`)
- `characters.fact_generation.draft_mode` (str_enum, default `deterministic`, allowed: `deterministic`, `llm`)

## Snapshot

Settings are stored per campaign in `campaign.json` under `settings_snapshot`.
Each valid patch increments `settings_revision`.

## Validation

- Type checks enforced per definition.
- Range enforced for `rollback.max_checkpoints` (`0..10`).
- Mutual exclusion: `context.full_context_enabled` and
  `context.compress_enabled` cannot both be `true`.
- `dialog.strict_semantic_guard=true` enables hard `422` rejection for severe
  invalid `dialog_type` outputs; default `false` preserves fallback behavior.
- `dialog.conflict_text_checks_enabled=true` enables text-based conflict checks;
  default `false` keeps the existing non-text baseline behavior.
- `dialog.turn_profile_trace_enabled=true` enables optional `debug.used_profile_hash`
  in `/api/v1/chat/turn` responses; default `false` omits `debug`.

## API

### GET /api/v1/settings/schema?campaign_id=...

Returns `definitions` and the current `snapshot`.

### POST /api/v1/settings/apply

Request:

```json
{
  "campaign_id": "camp_0001",
  "patch": {
    "dialog.auto_type_enabled": false,
    "rollback.max_checkpoints": 3
  }
}
```

Response:

```json
{
  "snapshot": {
    "context": {
      "full_context_enabled": true,
      "compress_enabled": false
    },
    "rules": {
      "hp_zero_ends_game": true
    },
    "rollback": {
      "max_checkpoints": 3
    },
    "dialog": {
      "auto_type_enabled": false,
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
  "change_summary": [
    "dialog.auto_type_enabled",
    "rollback.max_checkpoints"
  ]
}
```

## Extending

To add a new setting:

1. Add a new `SettingDefinition` entry in `backend/domain/settings.py`.
2. Add a field to `SettingsSnapshot` in `backend/domain/models.py`.
3. Update `docs/01_specs/storage_layout.md` and this document.
