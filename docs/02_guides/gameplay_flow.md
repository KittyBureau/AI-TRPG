# Complete Gameplay Flow Guide (MVP)

## Purpose

This guide documents the complete MVP loop from campaign creation to at least one completed turn:

1. `create_campaign`
2. `world_generate`
3. `map_generate`
4. `actor_spawn`
5. `move`
6. `chat/turn`

It covers both API-first usage and the minimal frontend flow controls.

## Important Constraint

The backend currently exposes `world_generate`, `map_generate`, `actor_spawn`, and `move` as tool calls executed inside `POST /api/v1/chat/turn`. There are no dedicated HTTP endpoints for these tools.

Because of this, frontend flow buttons trigger tool execution through templated `user_input` in `/api/v1/chat/turn`.

- This can be non-deterministic depending on model behavior.
- The UI supports small retries for tool steps.

## Backend Endpoints Used In This Flow

- `POST /api/v1/campaign/create`
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

### 6) Submit one regular turn

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

## Frontend Minimal Flow (single page)

Open `frontend/index.html` through a static server and set Base URL.

The page now includes these flow panels:

- `World Setup`
- `Actor Spawn`
- `Move`
- `Flow Buttons`

### Manual step buttons

Use the following buttons in order:

1. `Create Campaign` (existing Connection panel)
2. `Generate World`
3. `Generate Map`
4. `Spawn Actor`
5. `Move`
6. `Submit Turn`

### One-click chain

Use `Run Full Flow` in `Flow Buttons` to run:

- create campaign -> world -> map -> spawn -> move -> turn

The flow result is shown in the panel output.

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
- retries for tool steps are controlled by `Tool Retry Attempts` (1..5).

## What to inspect after running

- turn response:
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
