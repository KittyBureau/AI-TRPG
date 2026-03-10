# AI-TRPG Project Status (Playable v1)

## 0. Baseline Closure

- Playable v1 baseline closed on 2026-03-10.
- Closed baseline coverage: world generation, explicit world-aware campaign creation, repeatable play loop, read-only World Preview, authoritative Map Panel, backend narrative fallback for successful tool-only turns, and stable Character Library typing during Play-page rerenders.
- Remaining tracked follow-up items are post-baseline polish only: null-position actor closure and current-turn result visibility cleanup.
- Current baseline is suitable as the next-stage starting point without reopening the closed playable loop.

## 1. Architecture Overview

Backend:

- FastAPI routes under `backend/api/`
- application services under `backend/app/`
- pure domain rules under `backend/domain/`
- storage and resource IO under `backend/infra/` and `backend/services/`

Frontend:

- static-module frontend rooted at `frontend/`
- `play.html` for the playable loop
- `debug.html` for request/trace inspection
- shared API layer, store, and panel modules
- Play page currently includes Campaign, World, World Preview, Character Library, Party, Map, Actor Control, and Debug panels

Storage:

- persistent data under `storage/`
- campaign state under `storage/campaigns/`
- world state under `storage/worlds/`
- character library under `storage/characters_library/`
- runtime config and secrets under `storage/config/` and `storage/secrets/`

Runtime system:

- backend startup performs a non-interactive credential readiness probe
- runtime readiness is exposed through `/api/v1/runtime/status`
- explicit local unlock is handled by `python -m backend.tools.unlock_keyring`

## 2. Stable Runtime Flow

1. Start backend.
2. Check `GET /api/v1/runtime/status`.
3. If `ready=false` and `reason=passphrase_required`, run `python -m backend.tools.unlock_keyring`.
4. CLI posts passphrase to `POST /api/v1/runtime/unlock`.
5. Runtime status becomes `ready=true`.
6. Frontend detects readiness and recovers campaign/session state.
7. `POST /api/v1/chat/turn` executes the current actor turn.

## 3. Frontend Structure

- `frontend/api/`: HTTP helpers and backend base URL handling
- `frontend/store/`: shared runtime state, readiness checks, recovery flow
- `frontend/panels/`: campaign, party, actor control, debug, and related panels
- `frontend/play.js`: playable entrypoint
- `frontend/debug.js`: debug entrypoint

## 4. Backend Systems

- chat turn execution via `POST /api/v1/chat/turn`
- tool execution and validation in the tool executor
- deterministic stub `world_generate`
- validated `map_generate` with rollback on invalid graphs
- inventory authority through `inventory_add`
- scene interaction MVP through `scene_action`

## 5. Storage Model

- `storage/campaigns/<campaign_id>/campaign.json`
- `storage/campaigns/<campaign_id>/turn_log.jsonl`
- `storage/worlds/<world_id>/world.json`
- `campaign.json.actors[*]` as runtime actor authority
- `campaign.json.entities` for scene interaction state
- `turn_log.jsonl` for append-only turn audit

## 6. Current Stable Capabilities

- world generation and world listing from Play
- explicit world-aware campaign creation
- playable gameplay loop from campaign selection to turn execution
- campaign load and authoritative refresh
- active actor control and switching
- read-only World Preview derived from shared campaign/world snapshot state
- read-only current-situation Map Panel derived from authoritative campaign snapshot state
- successful tool-only turns keep readable `narrative_text` via backend fallback
- Character Library typing remains stable during normal rerender/refresh paths
- move / inventory / scene action flow
- runtime unlock flow via status + explicit CLI
- frontend recovery from not-ready backend
- debug panel request/response inspection

## 7. Known Constraints

- keyring requires local unlock when credentials are not already available
- frontend requires backend running at the configured base URL
- storage/config/secrets files must exist for real LLM credentials
- frontend readiness recovery depends on runtime polling or manual retry, not browser-level live push

## 8. Next Development Candidates

- full world generator beyond deterministic stub
- world content and entity expansion
- UI improvements beyond the current panel MVP
- multiplayer/session coordination
- broader AI behavior and content-quality improvements
