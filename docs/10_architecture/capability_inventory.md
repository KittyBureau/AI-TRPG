# Capability Inventory (Runtime Snapshot)

Last updated: 2026-03-05

## A. Run and Entry

- API app entry: `backend/api/main.py` (`app = create_app()`).
- Startup command: `uvicorn backend.api.main:app --reload`.
- OpenAPI/docs:
  - `/api/v1/openapi.json`
  - `/api/v1/docs`
  - `/api/v1/redoc`

## B. HTTP Endpoints (Current)

Campaign:

- `POST /api/v1/campaign/create`
- `GET /api/v1/campaign/list`
- `POST /api/v1/campaign/select_actor`
- `GET /api/v1/campaign/get`
- `GET /api/v1/campaign/status`
- `POST /api/v1/campaign/milestone/advance`

Chat/Tools:

- `POST /api/v1/chat/turn`

Settings:

- `GET /api/v1/settings/schema`
- `POST /api/v1/settings/apply`

Map/World:

- `GET /api/v1/map/view`
- `GET /api/v1/campaigns/{campaign_id}/world`

Character library:

- `GET /api/v1/characters/library`
- `GET /api/v1/characters/library/{character_id}`
- `POST /api/v1/characters/library`
- `POST /api/v1/campaigns/{campaign_id}/party/load`

Character fact:

- `POST /api/v1/campaigns/{campaign_id}/characters/generate`
- `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches`
- `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches/{request_id}`
- `GET /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}`
- `POST /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt`

## C. Storage and Authority

- Storage root: `storage/`
- Campaign: `storage/campaigns/<campaign_id>/campaign.json`
- Turn log: `storage/campaigns/<campaign_id>/turn_log.jsonl`
- World: `storage/worlds/<world_id>/world.json`
- Character library: `storage/characters_library/<character_id>.json`

Authority:

- runtime actor state authority is `campaign.actors[*]`
- legacy mirrors (`positions`, `hp`, `character_states`, `state.positions*`) are compatibility fields

## D. External Resources and Trace

- Manifest: `resources/manifest.json`
- Loader: `backend/infra/resource_loader.py`
- Trace gate setting: `dialog.turn_profile_trace_enabled`
- Trace contract: `debug.resources` (+ legacy debug compatibility fields)

## E. Frontend Runtime

- Recommended entry: `frontend/play.html`
- Debug entry: `frontend/debug.html`
- Deprecated redirect: `frontend/index.html`
- Panel registry: `frontend/panels/registry.js`

## F. Regression Entry

- API guide: `docs/20_runtime/testing/api_test_guide.md`
- Gameplay guide: `docs/20_runtime/gameplay_flow.md`
- Deterministic smoke scripts:
  - `scripts/smoke_world_generate.ps1`
  - `scripts/smoke_full_gameplay.ps1`
  - `scripts/smoke_frontend_flow.ps1`
