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

Notes:
- CORS is enabled for `http://localhost:*` and `http://127.0.0.1:*` in `backend/api/main.py`.
- Opening the HTML directly via `file://` is not recommended; use a static server.

## What it does

- Sends raw JSON exactly as typed (no validation).
- Displays response fields + raw response.
- Records each request/response in local history with export/copy tools.
- Includes a V1.1 operations panel for quick verification of lifecycle/milestone/settings/adoption workflows.

## V1.1 quick operations in UI

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

### Settings focus toggles

The panel can patch key V1.1 switches through `POST /api/v1/settings/apply`:

- `dialog.strict_semantic_guard`
- `dialog.conflict_text_checks_enabled`
- `context.compress_enabled`

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
