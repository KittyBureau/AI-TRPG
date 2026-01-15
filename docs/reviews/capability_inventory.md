# Capability Inventory
## A. How to Run
- Entry point: `backend/api/main.py` defines `app = create_app()` and includes routers.
- Startup command (docs): `uvicorn backend.api.main:app --reload` (`README.md`, `docs/test/API_TEST_GUIDE.md`).
- Default port: not set in code; docs reference `http://127.0.0.1:8000` (`docs/test/人工测试说明文档.md`).
- Static files: no `StaticFiles` usage found (`backend/api/main.py`, no matches for `StaticFiles`).

## B. API Endpoints
- POST `/api/campaign/create` — create a new campaign with optional world/map/party/active actor (`backend/api/routes/campaign.py:create_campaign`).
- GET `/api/campaign/list` — list campaigns with id/world_id/active_actor_id (`backend/api/routes/campaign.py:list_campaigns`).
- POST `/api/campaign/select_actor` — set active actor for campaign (`backend/api/routes/campaign.py:select_actor`).
- POST `/api/chat/turn` — submit a user turn and receive narrative + state/tool info (`backend/api/routes/chat.py:submit_turn`).
- GET `/api/settings/schema` — get settings definitions and current snapshot (`backend/api/routes/settings.py:get_schema`).
- POST `/api/settings/apply` — apply settings patch to a campaign (`backend/api/routes/settings.py:apply_settings`).

## C. Request/Response Shapes
- Campaign create request/response (`backend/api/routes/campaign.py`):
```json
// POST /api/campaign/create
{
  "world_id": "world_001",
  "map_id": "map_001",
  "party_character_ids": ["pc_001"],
  "active_actor_id": "pc_001"
}
```
```json
{
  "campaign_id": "camp_0001"
}
```
- Campaign list response (`backend/api/routes/campaign.py`):
```json
{
  "campaigns": [
    {
      "id": "camp_0001",
      "world_id": "world_001",
      "active_actor_id": "pc_001"
    }
  ]
}
```
- Select actor request/response (`backend/api/routes/campaign.py`):
```json
{
  "campaign_id": "camp_0001",
  "active_actor_id": "pc_002"
}
```
```json
{
  "campaign_id": "camp_0001",
  "active_actor_id": "pc_002"
}
```
- Turn request/response (`backend/api/routes/chat.py`, `backend/domain/models.py`):
```json
// POST /api/chat/turn
{
  "campaign_id": "camp_0001",
  "user_input": "I look around.",
  "actor_id": "pc_001"
}
```
```json
{
  "narrative_text": "string",
  "dialog_type": "scene_description",
  "tool_calls": [],
  "applied_actions": [],
  "tool_feedback": null,
  "conflict_report": null,
  "state_summary": {
    "active_actor_id": "pc_001",
    "positions": {},
    "positions_parent": {},
    "positions_child": {},
    "hp": {},
    "character_states": {}
  }
}
```
- Settings schema request/response (`backend/api/routes/settings.py`, `backend/domain/settings.py`):
```json
// GET /api/settings/schema?campaign_id=camp_0001
{
  "definitions": [
    {
      "key": "context.full_context_enabled",
      "type": "bool",
      "default": true,
      "scope": "campaign",
      "validation": {},
      "ui_hint": "toggle",
      "effect_tags": ["context"]
    }
  ],
  "snapshot": {
    "context": { "full_context_enabled": true, "compress_enabled": false },
    "rules": { "hp_zero_ends_game": true },
    "rollback": { "max_checkpoints": 0 },
    "dialog": { "auto_type_enabled": true }
  }
}
```
- Settings apply request/response (`backend/api/routes/settings.py`, `backend/domain/settings.py`):
```json
{
  "campaign_id": "camp_0001",
  "patch": {
    "dialog.auto_type_enabled": false
  }
}
```
```json
{
  "snapshot": {
    "context": { "full_context_enabled": true, "compress_enabled": false },
    "rules": { "hp_zero_ends_game": true },
    "rollback": { "max_checkpoints": 0 },
    "dialog": { "auto_type_enabled": false }
  },
  "change_summary": ["dialog.auto_type_enabled"]
}
```

## D. Storage Layout & Files Written
- Root storage directory: `storage/` (used by `backend/infra/file_repo.py`).
- Campaign data: `storage/campaigns/<campaign_id>/campaign.json` (create/update in `backend/infra/file_repo.py:create_campaign/save_campaign`).
- Turn logs: `storage/campaigns/<campaign_id>/turn_log.jsonl` (append in `backend/infra/file_repo.py:append_turn_log`).
- LLM config: `storage/config/llm_config.json` (read in `backend/services/llm_config.py:load_llm_config`).
- Keyring: `storage/secrets/keyring.json` (created/read in `backend/services/keyring.py`).
- `campaign.json` fields defined by `backend/domain/models.py:Campaign` and detailed in `docs/02_storage_layout.md`.

## E. Conversation Pipeline
- Turn orchestration: `backend/app/turn_service.py:TurnService.submit_turn`.
- LLM call: `backend/infra/llm_client.py:LLMClient.generate` uses OpenAI-compatible `chat/completions`.
- System prompt construction (includes allowlist, settings, map, state): `backend/app/turn_service.py:_build_system_prompt`.
- Dialog type handling: `backend/app/turn_service.py:_resolve_dialog_type` uses LLM output, fallback to `DEFAULT_DIALOG_TYPE` in `backend/domain/dialog_rules.py`.
- Conflict detection + retry: `backend/app/conflict_detector.py:detect_conflicts`, retry loop in `backend/app/turn_service.py` (max retries = 2), debug append `_build_debug_append`.
- Conflict types and behavior also described in `docs/07_conflict_and_retry.md`.
- No evidence of summary compression, persona lock, or explicit routing beyond dialog_type fallback (see `backend/app/turn_service.py`, `backend/domain/dialog_classifier.py` is currently stubbed and not used).

## F. Tooling System
- Tool allowlist stored per campaign: `backend/domain/models.py:Campaign.allowlist`, persisted in `campaign.json`.
- Execution entry: `backend/app/tool_executor.py:execute_tool_calls`.
- Allowed tools implemented:
  - `move` (`backend/app/tool_executor.py:_apply_move`)
  - `hp_delta` (`backend/app/tool_executor.py:_apply_hp_delta`)
  - `map_generate` (`backend/app/tool_executor.py:_apply_map_generate`, generator in `backend/infra/map_generators/deterministic_generator.py`)
- Permission checks: `backend/domain/state_machine.py:resolve_tool_permission`.
- Tool feedback structure: `backend/domain/models.py:ToolFeedback`, `FailedCall` with `status` and `reason`; produced in `backend/app/tool_executor.py`.
- Tool specs documented in `docs/05_tools.md`.

## G. Settings System
- Definitions registry and validation: `backend/domain/settings.py` (keys, types, validation, mutual exclusion).
- Snapshot model: `backend/domain/models.py:SettingsSnapshot`.
- Apply logic and revision increment: `backend/app/settings_service.py:apply_patch` updates `settings_revision`.
- API endpoints: `backend/api/routes/settings.py` (`/schema`, `/apply`).
- Storage location in campaign: `campaign.json.settings_snapshot` + `settings_revision` (see `docs/02_storage_layout.md`).

## H. Existing Frontend Pages
- No `.html` files found; no static serving configuration (`rg --files -g "*.html"` and no `StaticFiles` in backend).

## I. Test Utilities / Scripts
- Python tests:
  - `backend/tests/test_map.py` — end-to-end-ish map_generate behavior via API assumptions.
  - `backend/tests/test_map_generate.py` — unit-style tests for tool execution.
- Manual test guides:
  - `docs/test/API_TEST_GUIDE.md` — step-by-step API flows.
  - `docs/test/人工测试说明文档.md` — manual map_generate regression/smoke guide (mentions `MAP_TEST_STRICT`, `MAP_TEST_MAX_ATTEMPTS`).

## J. Unknowns / Gaps (evidence-based)
- Default port not set in code; only mentioned in docs (`docs/test/人工测试说明文档.md`).
- Dialog type classifier in `backend/domain/dialog_classifier.py` exists but is not wired into `TurnService` (code currently uses LLM output + fallback in `backend/app/turn_service.py`).
- Some docs reference `FakeLLM` flow (e.g., `docs/01_architecture.md`), but runtime code uses `LLMClient` (`backend/infra/llm_client.py`); this mismatch is not clarified in code.
