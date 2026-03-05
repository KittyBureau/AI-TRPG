# Complete Gameplay Flow Guide (MVP)

## Purpose

This guide documents the complete MVP loop from campaign creation to at least one completed turn:

1. `create_campaign`
2. `world_generate`
3. `map_generate`
4. `actor_spawn`
5. `move`
6. `scene_action`
7. `inventory_add`
7. `chat/turn`

It covers both API-first usage and the minimal frontend flow controls.

## Important Constraint

The backend currently exposes `world_generate`, `map_generate`, `actor_spawn`, `move`, `scene_action`, and `inventory_add` as tool calls executed inside `POST /api/v1/chat/turn`. There are no dedicated HTTP endpoints for these tools.

Because of this, frontend flow buttons trigger tool execution through templated `user_input` in `/api/v1/chat/turn`.

- This can be non-deterministic depending on model behavior.
- The UI supports small retries for tool steps.

Turn actor context:

- Preferred: send `execution.actor_id` in turn request.
- Compatibility: top-level `actor_id` is still accepted.
- Response includes `effective_actor_id` so frontend can confirm who executed the turn.
- If tool calls include `args.actor_id`, it must match `effective_actor_id`; mismatch is rejected with `actor_context_mismatch`.
- Same-campaign turn execution is serialized; concurrent requests can return `409 Conflict`.

## Backend Endpoints Used In This Flow

- `POST /api/v1/campaign/create`
- `GET /api/v1/campaign/get` (authoritative selected/actors snapshot for one campaign)
- `POST /api/v1/campaign/select_actor` (manual active actor switch)
- `GET /api/v1/characters/library` (optional for library inspect)
- `POST /api/v1/campaigns/{campaign_id}/party/load` (optional for deterministic party load)
- `POST /api/v1/chat/turn`
- `GET /api/v1/map/view` (optional for inspection)
- `GET /api/v1/campaigns/{campaign_id}/world` (optional for inspection)

## API Sequence (curl examples)

Set base URL:

```bash
BASE="http://127.0.0.1:8000"
```

### 1) Create campaign

```bash
curl -sS -X POST "$BASE/api/v1/campaign/create" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Example response:

```json
{ "campaign_id": "camp_0001" }
```

### 2) Trigger `world_generate` via turn

```bash
curl -sS -X POST "$BASE/api/v1/chat/turn" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "user_input":"[UI_FLOW_STEP] Return JSON with keys assistant_text, dialog_type, tool_calls. Execute exactly one tool_call now: world_generate. Use args exactly: {\"world_id\":\"world_ui_flow_v1\",\"bind_to_campaign\":true}. Do not call any additional tools. Keep assistant_text empty."
  }'
```

Expected check:

- `applied_actions[*].tool` contains `world_generate`

### 3) Trigger `map_generate` via turn

```bash
curl -sS -X POST "$BASE/api/v1/chat/turn" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "user_input":"[UI_FLOW_STEP] Return JSON with keys assistant_text, dialog_type, tool_calls. Execute exactly one tool_call now: map_generate. Use args exactly: {\"parent_area_id\":\"area_001\",\"theme\":\"UI Path\",\"constraints\":{\"size\":3,\"seed\":\"ui-flow\"}}. Do not call any additional tools. Keep assistant_text empty."
  }'
```

Expected check:

- `applied_actions[*].tool` contains `map_generate`

### 4) Trigger `actor_spawn` via turn

```bash
curl -sS -X POST "$BASE/api/v1/chat/turn" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "user_input":"[UI_FLOW_STEP] Return JSON with keys assistant_text, dialog_type, tool_calls. Execute exactly one tool_call now: actor_spawn. Use args exactly: {\"character_id\":\"char_ui_support\",\"bind_to_party\":true}. Do not call any additional tools. Keep assistant_text empty."
  }'
```

Expected check:

- `applied_actions[*].tool` contains `actor_spawn`

### 5) Trigger `move` via turn

```bash
curl -sS -X POST "$BASE/api/v1/chat/turn" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "user_input":"[UI_FLOW_STEP] Return JSON with keys assistant_text, dialog_type, tool_calls. Execute exactly one tool_call now: move. Use args exactly: {\"actor_id\":\"pc_001\",\"to_area_id\":\"area_002\"}. Do not call any additional tools. Keep assistant_text empty."
  }'
```

Expected check:

- `applied_actions[*].tool` contains `move`

### 6) Trigger `inventory_add` via turn

```bash
curl -sS -X POST "$BASE/api/v1/chat/turn" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "user_input":"[UI_FLOW_STEP] Return JSON with keys assistant_text, dialog_type, tool_calls. Execute exactly one tool_call now: inventory_add. Use args exactly: {\"item_id\":\"torch\",\"quantity\":1}. Do not call any additional tools. Keep assistant_text empty."
  }'
```

Expected check:

- `applied_actions[*].tool` contains `inventory_add`

### Scene interaction (`scene_action`) via turn

```bash
curl -sS -X POST "$BASE/api/v1/chat/turn" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "user_input":"[UI_FLOW_STEP] Return JSON with keys assistant_text, dialog_type, tool_calls. Keep assistant_text empty. Execute exactly one tool_call now: scene_action. Use args exactly: {\"actor_id\":\"pc_001\",\"action\":\"inspect\",\"target_id\":\"door_01\",\"params\":{}}. Do not call any additional tools.",
    "execution":{"actor_id":"pc_001"}
  }'
```

Expected check:

- `applied_actions[*].tool` contains `scene_action`
- `applied_actions[*].result.ok` exists
- entity deltas are reflected in `campaign.json.entities`

### 7) Submit one regular turn

```bash
curl -sS -X POST "$BASE/api/v1/chat/turn" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "user_input":"Describe the current scene without calling tools."
  }'
```

Expected check:

- response includes `narrative_text` (non-empty preferred)

### 8) Manually switch active actor

```bash
curl -sS -X POST "$BASE/api/v1/campaign/select_actor" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"camp_0001",
    "active_actor_id":"pc_001"
  }'
```

Expected check:

- response `active_actor_id` equals requested actor
- actor must already be in `selected.party_character_ids`

### 9) Refresh campaign authoritative state

```bash
curl -sS "$BASE/api/v1/campaign/get?campaign_id=camp_0001"
```

Expected check:

- response includes `selected.party_character_ids`
- response includes `selected.active_actor_id`

## Frontend Minimal Flow

Open `frontend/play.html` through a static server and set Base URL.

For entrypoint/deprecation policy details, also see `docs/20_runtime/frontend_entrypoints.md`.

Page roles:

- `play.html`: player-facing round execution (panel architecture, no raw JSON).
- `debug.html`: debug-facing request builder + raw response + trace export.
- `index.html`: deprecated landing/redirect page to `play.html` (no legacy app logic execution).

Play architecture (module-based):

```text
frontend/
  play.html
  debug.html
  styles.css
  api/api.js
  store/store.js
  panels/*.js
  models/log_entry.js
  renderers/delta_renderer.js
```

The page now includes these flow panels:

- `Campaign Panel`
- `Character Library Panel`
- `Party Panel`
- `Actor Control Panel`
- `Debug Panel`

### Manual step buttons

Use the following buttons in order:

1. `Create Campaign` or select existing campaign
2. In `Character Library`, load at least two characters into campaign
3. In `Party Panel`, use selector + `Set Active` to switch active actor
4. In `Actor Control Panel`, submit `Turn` or `Move`
5. In `Campaign Panel`, click `Refresh Campaign` to re-sync party/active from backend

State consistency verification:

- Run `docs/20_runtime/testing/state_consistency_check.md` after Play state/store changes.

## Play page Round MVP

`play.html` provides a deterministic panel flow:

1. Select campaign.
2. Load characters from library to party.
3. Switch active actor manually in `Party Panel` when needed.
4. Send turn or move with selected actor in `Actor Control Panel`.

Each step calls `/api/v1/chat/turn` sequentially with:

```json
{
  "campaign_id": "camp_0001",
  "user_input": "actor action input",
  "execution": { "actor_id": "pc_001" }
}
```

Notes:

- `party/load` only auto-sets active actor when current active is empty.
- To force a switch, use `Party Panel -> Set Active` (calls `/api/v1/campaign/select_actor`).
- Turn response `effective_actor_id` is the source of truth for execution identity.

## Frontend lightweight regression script

Use this script to validate the frontend gameplay flow protocol quickly (without browser automation):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1
```

Optional:

- `-RetryAttempts 3` (range `1..5`)
- `-KeepWorkspace`

## UI defaults and rules

- `actor_spawn.character_id` is required in UI.
- `actor_spawn.bind_to_party` defaults to `true`.
- blank `spawn_position` uses backend default behavior.
- move input is minimal (`to_area_id` required); no `move_options` coupling in this version.
- objective / area description / inventory are displayed from `state_summary` extensions in turn response.
- retries for tool steps are controlled by `Tool Retry Attempts` (1..5).

## What to inspect after running

- turn response:
  - `effective_actor_id`
  - `narrative_text`
  - `tool_calls`
  - `applied_actions`
  - `tool_feedback`
  - `state_summary`
- optional files:
  - `storage/campaigns/<campaign_id>/campaign.json`
  - `storage/campaigns/<campaign_id>/turn_log.jsonl`
  - `storage/worlds/<world_id>/world.json`

## Known limits

- Tool triggering through natural language is model-dependent.
- Retries reduce but do not eliminate non-determinism.
- Dedicated per-tool HTTP APIs are not part of current architecture.
