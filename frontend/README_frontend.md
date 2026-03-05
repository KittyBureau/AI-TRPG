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
- `http://127.0.0.1:5173/index.html` (deprecated landing page, auto-redirects to Play)

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
  - For manual verification of refresh + active consistency, run:
    - `docs/02_guides/testing/state_consistency_check.md`
- `frontend/debug.html`:
  - Request Builder, Response Viewer, Trace Log.
  - Copy request/response and export reproduction bundle.
- `frontend/index.html`:
  - Deprecated landing page only.
  - No longer loads `app.js` legacy flow logic.
  - Provides link + auto redirect to `play.html`.

## Legacy flow note

Legacy raw-console operations are soft-deprecated. For reproducible checks:

- Use `frontend/play.html` for gameplay flow.
- Use `frontend/debug.html` for raw request/response checks.
- Use `docs/02_guides/testing/api_test_guide.md` for endpoint-level verification.

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
