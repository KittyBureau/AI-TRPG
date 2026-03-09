# API Test Guide (Authoritative)

Last updated: 2026-03-06

This is the single authoritative API test guide.

## 1. Preconditions

1. Start backend:

```bash
uvicorn backend.api.main:app --reload
```

2. Optional real LLM setup:

- copy `storage/config/llm_config.example.json` -> `storage/config/llm_config.json`
- configure profile
- backend startup performs a non-interactive credential precheck
- if `GET /api/v1/runtime/status` returns `{"ready": false, "reason": "passphrase_required"}`, run:

```bash
python -m backend.tools.unlock_keyring
```

- `POST /api/v1/runtime/unlock` is reserved for the local unlock command; the frontend does not collect passphrases
- `GET /api/v1/runtime/status` returns `{"ready": true|false, "reason": "..."}` for frontend/readiness checks
- backend startup no longer blocks on `getpass()`; unlock happens only through the explicit local CLI

3. Base URL:

```bash
BASE=http://127.0.0.1:8000
```

## 2. Deterministic Regression (Recommended First)

Run these scripts from repo root:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1
powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1
```

Optional artifact retention:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1 -KeepWorkspace
powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1 -KeepWorkspace
```

Primary pass criteria:

- campaign/world/turn log files generated and coherent
- tool chain success (`world_generate -> map_generate -> actor_spawn -> move`)
- final narrative-only turn returns non-empty `narrative_text`

## 3. Core API Contract Checks

Stable API endpoints used by the current playable loop:

- `GET /api/v1/runtime/status`
- `POST /api/v1/runtime/unlock`
- `GET /api/v1/campaign/list`
- `GET /api/v1/characters/library`
- `POST /api/v1/chat/turn`

### 3.1 Campaign create/list/get/select

- `POST /api/v1/campaign/create`
- `GET /api/v1/campaign/list`
- `GET /api/v1/campaign/get?campaign_id=...`
- `POST /api/v1/campaign/select_actor`

Checks:

- created campaign persisted under `storage/campaigns/<id>/campaign.json`
- `selected.party_character_ids` and `selected.active_actor_id` remain consistent
- `GET /campaign/get` returns actor id list from `campaign.actors`

### 3.2 Chat turn contract

Endpoint: `POST /api/v1/chat/turn`

Optional request hint:

- `context_hints.selected_item_id`
- when present, backend validates it against `actors[effective_actor_id].inventory`
- valid hint injects `selected_item` into turn context
- `selected_item` always includes `id` and `quantity`
- `selected_item` may also include `name` and `description` when item metadata is available
- metadata miss/load failure falls back to `{id, quantity}`
- invalid/missing hint is ignored silently and must not fail the turn

Response required keys:

- `effective_actor_id`
- `narrative_text`
- `dialog_type`
- `tool_calls`
- `applied_actions`
- `tool_feedback`
- `conflict_report`
- `state_summary`

Stable response semantics:

- top-level `debug` is omitted when trace is off
- top-level `debug` is present only when trace is on
- when trace is on and selected item validation succeeds, `debug.selected_item`
  may be present with minimal observability fields:
  - `id`
  - `has_metadata`
- `tool_feedback` may be `null` when there are no failed calls
- `conflict_report` may be `null` when no retry-exhausted conflict occurred
- `tool_calls` and `applied_actions` are always arrays
- `state_summary` is always present and must include:
  - `active_actor_id`
  - `positions`, `positions_parent`, `positions_child`
  - `hp`, `character_states`
  - `inventories`
  - `objective`
  - `active_area_id`, `active_area_name`, `active_area_description`
  - `active_actor_inventory`

Actor context priority:

- `execution.actor_id` -> top-level `actor_id` -> `selected.active_actor_id`

Mismatch rule:

- if tool `args.actor_id` differs from `effective_actor_id`, expect `tool_feedback.failed_calls[*].reason=actor_context_mismatch`

Concurrency rule:

- concurrent same-campaign turns may return `409` with "already running"

### 3.3 Runtime readiness contract

- `GET /api/v1/runtime/status`
- `POST /api/v1/runtime/unlock` (local CLI path)

Checks:

- startup precheck runs before frontend gameplay flow
- startup precheck is non-interactive and must not call `getpass()`
- `ready=false` with `reason=passphrase_required` means the developer should run `python -m backend.tools.unlock_keyring`
- other stable reasons include `config_missing`, `keyring_missing`, `credentials_unavailable`, `keyring_locked`
- `ready=true` means keyring/config probe has succeeded for the active LLM profile
- when frontend opens while `ready=false`, page chrome/panels should still render and show a retry/unlock hint
- after unlock, frontend should recover without full page refresh (polling or `Retry Connection`)
- frontend polling/state refresh must not churn focused turn inputs while waiting for readiness changes

### 3.4 Settings contract

- `GET /api/v1/settings/schema?campaign_id=...`
- `POST /api/v1/settings/apply`

Trace gate check:

1. default `dialog.turn_profile_trace_enabled=false`
   - `POST /chat/turn` should omit top-level `debug`
2. apply patch:

```json
{
  "campaign_id": "camp_0001",
  "patch": {
    "dialog.turn_profile_trace_enabled": true
  }
}
```

3. `POST /chat/turn` should include `debug.resources`

## 4. Debug/Trace Contract Checks

When trace is enabled:

- `debug.resources` must exist
- categories are arrays:
  - `prompts`, `flows`, `schemas`, `templates`, `policies`, `template_usage`

Legacy compatibility fields may also appear:

- `debug.prompt`, `debug.flow`, `debug.schemas`, `debug.templates`
- `debug.used_prompt_*`, `debug.used_flow_*`, `debug.used_profile_hash`

## 5. Storage Authority Checks

After tool calls, verify authority fields:

- `campaign.json.actors[*].position`
- `campaign.json.actors[*].hp`
- `campaign.json.actors[*].character_state`
- `campaign.json.actors[*].inventory`

Legacy mirrors (`positions/hp/character_states/state.positions*`) are compatibility fields, not authority.

## 6. Character Library / Character Fact Checks

### 6.1 Character Library

- `GET /api/v1/characters/library`
- `GET /api/v1/characters/library/{character_id}`
- `POST /api/v1/characters/library`
- `POST /api/v1/campaigns/{campaign_id}/party/load`

Checks:

- library files under `storage/characters_library/*.json`
- `party/load` writes `actors[character_id].meta.profile`

### 6.2 Character Fact

- `POST /api/v1/campaigns/{campaign_id}/characters/generate`
- `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches`
- `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches/{request_id}`
- `GET /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}`
- `POST /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt`

Checks:

- batch + draft files created in `storage/campaigns/<campaign_id>/characters/generated/`
- duplicate `request_id` returns `409`
- invalid request/payload returns expected `400/422`

## 7. Frontend-Related API Regression

Prefer runtime guides:

- `docs/20_runtime/gameplay_flow.md`
- `docs/20_runtime/testing/active_actor_integration_smoke.md`
- `docs/20_runtime/testing/state_consistency_check.md`

`frontend/index.html` is deprecated redirect only.

## 8. Exit Criteria

Minimum regression pass for API changes:

1. three smoke scripts pass
2. trace gate check passes
3. core create/list/get/select + turn contract checks pass
4. storage authority checks pass
5. Set B 10-turn manual record is completed for release-gate verification
6. if character modules touched, character library/fact checks pass
