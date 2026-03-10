# Frontend Entrypoints (Runtime)

## Current Entry Policy

- Recommended gameplay entry: `frontend/play.html`
- Recommended debug entry: `frontend/debug.html`
- Deprecated landing/redirect only: `frontend/index.html`

`frontend/index.html` should not be used for gameplay validation; it auto-redirects to Play UI.

## Panel Architecture

Current runtime frontend is panel-based and module-driven:

- state: `frontend/store/store.js`
- network API: `frontend/api/api.js`
- panel registry: `frontend/panels/registry.js`
- play bootstrap: `frontend/play.js`
- debug bootstrap: `frontend/debug.js`

Play page panels:

- Campaign Panel
- World Panel
- Character Library Panel
- Party Panel
- Map Panel
- Actor Control Panel
- Debug Panel

Runtime readiness gate:

- Play and Debug pages query `GET /api/v1/runtime/status` during initialization.
- Frontend API calls target the backend base URL (local static-server development defaults to `http://127.0.0.1:8000`); they must not rely on relative `/api/v1/*` paths under the frontend static server.
- Play/Debug always mount their base panel framework first; `not ready` is treated as runtime state, not as a fatal page-init error.
- When `ready=false` with `reason=passphrase_required`, the UI keeps using the existing status area and tells the user to run `python -m backend.tools.unlock_keyring`.
- The frontend does not collect passphrases; startup no longer uses a background `getpass()` prompt, and recovery begins only after the backend reports `ready=true`.
- Play and Debug do a lightweight readiness re-check while blocked, so the page can recover after a successful local unlock.
- Play also exposes a minimal manual recovery action via `Retry Connection` in the Campaign panel; Debug exposes the same action in the Request Builder.
- Readiness polling must not rebuild focused text inputs on every cycle; repeated unchanged status checks should avoid full panel re-render, and focused textarea/input selection should survive the one-shot recovery refresh.

Stable runtime endpoints used by the frontend:

- `GET /api/v1/runtime/status`
- `POST /api/v1/runtime/unlock` (CLI-facing; frontend never posts passphrases)
- `GET /api/v1/worlds/list`
- `POST /api/v1/worlds/generate`
- `POST /api/v1/campaign/create`
- `GET /api/v1/campaign/list`
- `GET /api/v1/campaign/get`
- `POST /api/v1/campaign/select_actor`
- `GET /api/v1/characters/library`
- `POST /api/v1/campaigns/{campaign_id}/party/load`
- `POST /api/v1/chat/turn`

## Validation Entry

Deterministic smoke scripts:

- `scripts/smoke_frontend_flow.ps1`
- `scripts/smoke_full_gameplay.ps1`

Related guide:

- `docs/20_runtime/gameplay_flow.md`
- `docs/20_runtime/testing/active_actor_integration_smoke.md`
- `docs/20_runtime/testing/state_consistency_check.md`
