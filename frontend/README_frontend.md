# Raw Request Console (Frontend)

This is a static, framework-free UI for sending raw JSON requests to the FastAPI backend.

## Run (static)

1. Start the backend (default: `http://127.0.0.1:8000`).
2. Serve this folder with any static server.

Example using Python:

```bash
cd frontend
python -m http.server 5173
```

Then open `http://127.0.0.1:5173` and set **Base URL** to `http://127.0.0.1:8000`.
The map view page reads the same base URL from local storage.

Main entry points:
- `http://127.0.0.1:5173/play.html` (play mode, panel architecture)
- `http://127.0.0.1:5173/debug.html` (debug mode, raw request/response)
- `http://127.0.0.1:5173/index.html` (legacy raw console)

Notes:
- CORS is enabled for `http://localhost:*` and `http://127.0.0.1:*` in `backend/api/main.py`.
- Opening the HTML directly via `file://` is not recommended; use a static server.

## What it does

- Sends raw JSON exactly as typed (no validation).
- Displays response fields + raw response.
- Shows gameplay snapshot fields from `state_summary`: objective, active area description, and active actor inventory.
- Records each request/response in local history with export/copy tools.
- Includes a V1.1 operations panel for quick verification of lifecycle/milestone/settings/adoption workflows.

## Frontend architecture (panel-based)

Current Play/Debug architecture uses plain HTML + JavaScript modules:

```text
frontend/
  play.html
  debug.html
  styles.css
  play.js
  debug.js
  api/api.js
  store/store.js
  panels/campaign_panel.js
  panels/character_library_panel.js
  panels/party_panel.js
  panels/actor_control_panel.js
  panels/debug_panel.js
  models/log_entry.js
  renderers/delta_renderer.js
```

Key constraints implemented:
- `play.js` only initializes store and panel modules.
- State authority is centralized in `store/store.js`.
- Network calls are encapsulated in `api/api.js`.
- Panel modules render and dispatch store actions.

## Play vs Debug pages

- `frontend/play.html`:
  - Vertical panel flow:
    - `Campaign Panel`
    - `Character Library Panel`
    - `Party Panel`
    - `Actor Control Panel`
    - `Debug Panel`
  - `Party Panel` includes manual active actor switching:
    - Select actor from `party_character_ids`
    - Click **Set Active**
    - Calls `POST /api/v1/campaign/select_actor`
    - On success updates `campaign.active_actor_id` in store
  - `Campaign Panel` includes **Refresh Campaign**:
    - Calls `GET /api/v1/campaign/get?campaign_id=...`
    - Syncs `selected.party_character_ids` and `selected.active_actor_id` from backend authoritative state
- `frontend/debug.html`:
  - Request Builder, Response Viewer, Trace Log.
  - Copy request/response and export reproduction bundle.
- `frontend/index.html`:
  - Legacy raw console remains available for backward compatibility.

## V1.1 quick operations in legacy UI

The frontend now provides a **Campaign Status & V1.1 Ops** panel:

- `Fetch Campaign Status`
  - Calls `GET /api/v1/campaign/status?campaign_id=...`
  - Shows:
    - lifecycle: `ended`, `reason`, `ended_at`
    - milestone: `current`, `last_advanced_turn`, `turn_trigger_interval`, `pressure`, `pressure_threshold`, `summary`
- `Advance Milestone`
  - Calls `POST /api/v1/campaign/milestone/advance`
  - Request body:
    ```json
    {
      "campaign_id": "camp_0001",
      "summary": "manual checkpoint"
    }
    ```
- `Adopt Fact`
  - Calls `POST /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt`
  - Request body:
    ```json
    { "accepted_by": "system" }
    ```
- `Generate Facts`
  - Calls `POST /api/v1/campaigns/{campaign_id}/characters/generate`
  - Uses a raw JSON textarea so `party_context` can be pasted directly.
- `Run Loop`
  - Chains:
    1. `POST /api/v1/campaigns/{campaign_id}/characters/generate`
    2. `POST /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt`
    3. `POST /api/v1/chat/turn` (fixed short input: `Introduce yourself briefly.`)
    4. `GET /api/v1/campaign/status?campaign_id=...`
  - Shows compact combined output in **Character Loop** result panel.

### Settings focus toggles

The panel can patch key V1.1 switches through `POST /api/v1/settings/apply`:

- `dialog.strict_semantic_guard`
- `dialog.conflict_text_checks_enabled`
- `context.compress_enabled`
- `dialog.turn_profile_trace_enabled` (set via raw settings patch panel)

When toggling `context.compress_enabled`, the UI also patches
`context.full_context_enabled` inversely to satisfy backend mutual exclusion.

### Error and guard visibility

- `Latest API Error` shows:
  - HTTP status
  - backend `detail`
  - suggested action
- `Turn Guard Insight` highlights:
  - conflict/retry related hints
  - `repeat_illegal_request` suppression signals from `tool_feedback`

## Map view (V0)

Open `http://127.0.0.1:5173/map.html` to see the read-only map snapshot.

## Frontend flow regression script (legacy path, lightweight)

To quickly validate the frontend gameplay button chain protocol (without browser automation),
run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1
```

Optional flags:

- `-RetryAttempts 3` to increase tool-step retries (range: 1..5)
- `-KeepWorkspace` to keep artifacts under `.tmp/smoke_frontend_flow/<run_id>`

What it validates:

1. `create_campaign`
2. `world_generate` via templated `/api/v1/chat/turn`
3. `map_generate` via templated `/api/v1/chat/turn`
4. `actor_spawn` via templated `/api/v1/chat/turn`
5. `move` via templated `/api/v1/chat/turn`
6. one narrative-only `chat/turn` shape check (`narrative_text`, `state_summary`)
7. state snapshot visibility (`state_summary.active_actor_inventory`, area/objective fields)
8. play delta contract visibility (`actor_id`, `changed`, `position`, `hp`, `character_state`, `inventory`, `error`)
