# AI-TRPG Project Status (Playable v1)

## 0. Baseline Closure

- Playable v1 baseline closed on 2026-03-10.
- Closed baseline coverage: world generation, explicit world-aware campaign creation, repeatable play loop, read-only World Preview, authoritative Map Panel, backend narrative fallback for successful tool-only turns, and stable Character Library typing during Play-page rerenders.
- Item System Refactor closure completed on 2026-03-23: portable item authority is stack-based through `campaign.items`, frontend inventory/selection/submit flow is stack-first, `/api/v1/campaign/get` and turn `state_summary` expose `inventory_stacks`, and remaining compatibility seams are explicit derived/fallback-only behavior.
- Remaining tracked follow-up items are post-baseline polish only: null-position actor closure and current-turn result visibility cleanup.
- Current baseline is suitable as the next-stage starting point without reopening the closed playable loop.
- Additional fixed regression baseline: `test_watchtower_world` was verified end-to-end on 2026-03-11 and now serves as the source example for Scenario Template 0 extraction.

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

- preferred local-first backend startup is `python scripts/run_backend.py` from repo root
- first-time local credential/bootstrap helper is `python -m backend.tools.setup_keyring`
- backend startup performs a non-interactive credential readiness probe
- runtime readiness is exposed through `/api/v1/runtime/status`
- explicit local unlock is handled by `python -m backend.tools.unlock_keyring`

## 2. Stable Runtime Flow

1. If this is the first real local run and config/keyring files are missing, run `python -m backend.tools.setup_keyring`.
2. Start backend with `python scripts/run_backend.py` from repo root.
3. Check `GET /api/v1/runtime/status`.
4. If `ready=false` and `reason=passphrase_required`, run `python -m backend.tools.unlock_keyring`.
5. CLI posts passphrase to `POST /api/v1/runtime/unlock`.
6. Runtime status becomes `ready=true`.
7. Frontend detects readiness and recovers campaign/session state.
8. `POST /api/v1/chat/turn` executes the current actor turn.

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
- portable item authority through `campaign.items`
- `actors[*].inventory` as a derived compatibility inventory view
- frontend inventory authority derived from `inventory_stacks`
- `selected_stack_id` as the normal selection / submit path
- stack-authoritative `take` / `drop` / `detach` / item-side `use`
- scene interaction MVP through `scene_action`

## 5. Storage Model

- `storage/campaigns/<campaign_id>/campaign.json`
- `storage/campaigns/<campaign_id>/turn_log.jsonl`
- `storage/worlds/<world_id>/world.json`
- `campaign.json.actors[*]` as runtime actor authority
- `campaign.json.items[*]` as portable item authority
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
- backend, frontend store, selection/submit, and UI/debug aligned on stack-backed selection resolution
- runtime unlock flow via status + explicit CLI
- frontend recovery from not-ready backend
- debug panel request/response inspection

## 6A. Formal Gameplay Model & Alignment Layer

- Formal Gameplay Model is currently read-only, non-authoritative, and isolated from runtime authority, turn execution, and tool execution.
- Current implemented formal validation coverage includes:
  - `dependency_groups` with `all_of` / `any_of`
  - `multi_path_coverage`
  - `clue_support_coverage`
- Current implemented quality and audit outputs include:
  - `gate_quality_statuses`
  - `overall_quality_status`
  - gate-level and overall authoring audit summaries
- Current generator-side shaping outputs include:
  - `gate_clue`
  - `gate_clue_support_gap`
- Current preset alignment baseline:
  - `midnight_archive_world` is the aligned sample for the modern formal output shape
  - `test_watchtower_world` remains the legacy baseline
- Current preset-alignment planning outputs include:
  - `alignment_level` (`legacy` / `partial` / `aligned`)
  - `priority_hint` (`high` / `medium` / `low`)
  - remediation backlog output with `gap_type`, `recommended_target`, and structured backlog summary

## 7. Known Constraints

- keyring requires local unlock when credentials are not already available
- frontend requires backend running at the configured base URL
- storage/config/secrets files must exist for real LLM credentials
- frontend readiness recovery depends on runtime polling or manual retry, not browser-level live push

## 8. Next Development Candidates

- primary next track: `P2-11A Context Builder Infrastructure`
  - introduce the context-builder seam before `_build_system_prompt()`
  - keep authoritative runtime state outside the builder
- scenario generator v0 is already stabilized enough to serve as a regression/content baseline rather than the next primary implementation track
- limited world content and entity expansion in support of the scenario generator
- UI improvements beyond the current panel MVP
- multiplayer/session coordination
- broader AI behavior and content-quality improvements
