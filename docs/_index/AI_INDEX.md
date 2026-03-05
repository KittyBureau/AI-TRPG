# AI_INDEX

Purpose: a stable, sectioned index of code constraints and verification points.
Use this as the default reference for every task.

## 1. Repository Structure & Layer Boundaries
**Rules**
- `backend/api/` handles HTTP only and delegates to `backend/app/`; do not perform IO or state changes directly in routes.
- `backend/domain/` stays pure (no FastAPI or storage/LLM IO); it defines rules and models.
- `backend/infra/` owns IO (file storage, LLM client) and must not import `backend/api/`.
- All persisted data lives under `storage/`.
**Checks**
- Review imports for cross-layer violations (e.g., `rg "fastapi|backend\\.api" backend/domain`).
- Confirm file writes go through `backend/infra/file_repo.py` and `storage/`.
**Scope**
- `backend/api/**`, `backend/app/**`, `backend/domain/**`, `backend/infra/**`, `storage/**`.

## 2. API & Data Contracts
**Rules**
- Request/response shapes follow `backend/api/routes/*.py` and `backend/domain/models.py`.
- `/api/v1/chat/turn` responses include `narrative_text`, `dialog_type`, `tool_calls`, `applied_actions`, `tool_feedback`, `conflict_report`, and `state_summary`; optional top-level `debug` may appear when debug settings are enabled.
- `GET /api/v1/map/view` returns area context plus `entities_in_area` (backend-authoritative scene entities for current area).
- `/api/v1/chat/turn` actor context resolution uses `execution.actor_id` first, then top-level `actor_id`, then `campaign.selected.active_actor_id`; response includes `effective_actor_id`.
- `/api/v1/chat/turn` runs under a per-campaign serial lock; concurrent same-campaign turns return `409`.
- `/api/v1/campaigns/{campaign_id}/world` resolves `campaign.selected.world_id` and returns world data; returns `409` when world_id is empty.
- Character Library REST is deterministic and separate from chat-turn tool flow:
  - `GET /api/v1/characters/library`
  - `GET /api/v1/characters/library/{character_id}`
  - `POST /api/v1/characters/library`
  - `POST /api/v1/campaigns/{campaign_id}/party/load`
- Changes to `Campaign`, `TurnLogEntry`, or API payloads must update `docs/01_specs/storage_layout.md` and `docs/02_guides/testing/api_test_guide.md`.
**Checks**
- Run the API test guide for any changed endpoints.
- Compare JSON payloads against `backend/domain/models.py`.
**Scope**
- `backend/api/routes/**`, `backend/domain/models.py`, `docs/01_specs/storage_layout.md`, `docs/02_guides/testing/api_test_guide.md`.

## 3. Dialog Types & LLM Output Schema
**Rules**
- `dialog_type` must be one of `DIALOG_TYPES`; fallback to `DEFAULT_DIALOG_TYPE` and set `dialog_type_source` to `fallback`.
- LLM output JSON keys are `assistant_text`, `dialog_type`, `tool_calls`; non-JSON output becomes `assistant_text` only.
**Checks**
- Validate `DIALOG_TYPES` in `backend/domain/dialog_rules.py` when adding or removing types.
- Exercise `/api/v1/chat/turn` to confirm fallback behavior.
**Scope**
- `backend/domain/dialog_rules.py`, `backend/app/turn_service.py`, `docs/01_specs/dialog_types.md`.

## 4. Settings Registry & Validation
**Rules**
- Settings keys must exist in `backend/domain/settings.py`; unknown keys are rejected.
- `apply_settings_patch` enforces type/range rules and mutual exclusion; changed patches increment `settings_revision`.
- Settings are stored in `campaign.json.settings_snapshot`.
**Checks**
- Use `/api/v1/settings/schema` and `/api/v1/settings/apply` to verify definitions and patches.
- Update `docs/01_specs/settings.md` for any key changes.
**Scope**
- `backend/domain/settings.py`, `backend/app/settings_service.py`, `backend/api/routes/settings.py`, `docs/01_specs/settings.md`, `docs/01_specs/storage_layout.md`.

## 5. Tool Calls Protocol & Execution
**Rules**
- Each tool call includes `id`, `tool`, `args`; `tool` must be in `campaign.allowlist`.
- Invalid args return `tool_feedback.failed_calls` with `status`=`error` or `rejected` and a documented `reason`.
- Tool params and allowlist follow `docs/01_specs/tools.md`.
- `scene_action` is the default non-move scene interaction tool; move remains a separate tool.
- `Campaign.entities` is authoritative for scene object state and stable entity IDs.
- `move_options` is read-only and must not change positions or other state.
- Movement state changes require a `move` tool_call; narration alone does not change positions.
- Inventory gain requires an `inventory_add` tool_call; narration alone does not change inventory.
- Injury/healing narration requires an `hp_delta` tool_call.
- Actor-bound tool checks use the turn effective actor id (not UI-selected active actor by default).
- Tool `args.actor_id` must match effective actor id when provided; mismatch is rejected as `actor_context_mismatch`.
- `world_generate` is metadata-only in v1 (no map generation chain); missing resolved world id returns tool reason `world_id_missing`.
- `actor_spawn` creates runtime actors in `campaign.actors`; explicit invalid `spawn_position` returns `invalid_args`.
**Checks**
- Run `backend/tests/test_map_generate.py`, `backend/tests/test_move_options.py`, `backend/tests/test_world_generate_tool.py`, `backend/tests/test_actor_spawn_tool.py`, `backend/tests/test_inventory_add_tool.py`, `backend/tests/test_scene_action_tool.py`, and `backend/tests/test_scene_action_turn_api.py` when touching tool execution or validation.
- Review `docs/01_specs/tools.md` for param and reason updates.
**Scope**
- `backend/app/tool_executor.py`, `backend/app/world_service.py`, `backend/app/actor_service.py`, `backend/domain/models.py`, `docs/01_specs/tools.md`, `backend/tests/test_map_generate.py`, `backend/tests/test_move_options.py`, `backend/tests/test_world_generate_tool.py`, `backend/tests/test_actor_spawn_tool.py`, `backend/tests/test_inventory_add_tool.py`.

## 6. Storage Layout & Persistence
**Rules**
- Campaigns persist at `storage/campaigns/<campaign_id>/campaign.json`; turns append to `turn_log.jsonl` via `FileRepo`.
- Character library persists at `storage/characters_library/<character_id>.json`.
- Worlds persist at `storage/worlds/<world_id>/world.json`; v1 API may lazily create a deterministic stub world on first read.
- LLM config lives at `storage/config/llm_config.json`; keyring at `storage/secrets/keyring.json` with no env fallback.
- Storage fields match `docs/01_specs/storage_layout.md`.
**Checks**
- Run the API test guide to verify files are written with expected shapes.
- Inspect storage files after changes to models or persistence logic.
**Scope**
- `backend/infra/file_repo.py`, `backend/services/llm_config.py`, `backend/services/keyring.py`, `storage/**`, `docs/01_specs/storage_layout.md`.

## 7. Map Data Integrity & Generation
**Rules**
- `reachable_area_ids` is authoritative; `map.connections` is derived and normalized.
- Map validation requires string reachable ids, no duplicates, no self loops, valid targets, and connected graphs per parent group.
- `map_generate` reverts on invalid maps and enforces `size` in `1..30`.
**Checks**
- Run `backend/tests/test_map_generate.py` and follow `docs/02_guides/testing/map_generate_manual_test.md`.
- Review `backend/domain/map_models.py` for validation logic.
**Scope**
- `backend/domain/map_models.py`, `backend/app/tool_executor.py`, `docs/01_specs/storage_layout.md`, `docs/02_guides/testing/map_generate_manual_test.md`.

## 8. Conflict Detection & Retry
**Rules**
- Detect conflicts before logging; do not persist campaign or turn log when conflicts exist.
- Retry with debug append up to 2 times; on failure return `conflict_report` without logging.
- Conflict types include `state_mismatch`, `tool_result_mismatch`, `forbidden_change`.
- Text-based conflict checks are disabled by default; set `CONFLICT_TEXT_CHECKS=1` to enable narrative keyword checks (rule_explanation only checks forbidden change when enabled).
**Checks**
- Review `backend/app/conflict_detector.py` and retry loop in `backend/app/turn_service.py`.
- Exercise retry scenarios via the API test guide.
**Scope**
- `backend/app/conflict_detector.py`, `backend/app/turn_service.py`, `docs/01_specs/conflict_and_retry.md`.

## 9. State Machine & Tool Permissions
**Rules**
- Allowed states: `alive`, `dying`, `unconscious`, `restrained_permanent`, `dead`.
- `dying` only allows `hp_delta` with positive delta on the actor; other non-alive states reject all tools.
- `rules.hp_zero_ends_game` drives state transitions on HP changes.
- `world_generate` and `actor_spawn` follow standard tool permission gates (`alive` allowed when in allowlist; non-alive restricted).
**Checks**
- Review `backend/domain/state_machine.py` and tool executor behavior.
- Add or update tests when changing state permission logic.
**Scope**
- `backend/domain/state_machine.py`, `backend/app/tool_executor.py`, `docs/01_specs/state_machine.md`.

## 10. Tests & Gatekeeping
**Rules**
- API contract changes require updating `docs/02_guides/testing/api_test_guide.md`.
- Tool/state/map changes require running `backend/tests/test_map_generate.py`, `backend/tests/test_move_options.py`, and reviewing the manual map_generate guide when map logic changes.
- `world_generate` changes require running `backend/tests/test_world_generate_tool.py` and the local smoke script `scripts/smoke_world_generate.ps1` (guide: `docs/02_guides/testing/world_generate_smoke_test.md`).
- Frontend gameplay flow UI/protocol changes require running `scripts/smoke_frontend_flow.ps1` and checking `frontend/README_frontend.md` + `docs/02_guides/gameplay_flow.md` for sync.
- Play Action Planner supports structured envelopes (`move` / `scene_action`) and compiles one strict `UI_FLOW_STEP` per step.
- Round play delta contract is frontend-owned in `frontend/play.js` and must keep stable keys: `actor_id`, `changed`, `position`, `hp`, `character_state`, `inventory`, `error`.
- Spec changes in `docs/01_specs/**` must be reflected in this AI_INDEX.
**Checks**
- Run targeted tests and document results in the task output.
- Update `docs/_index/ai_index_manifest.json` if paths or sections change.
**Scope**
- `backend/tests/**`, `docs/02_guides/testing/**`, `docs/01_specs/**`, `docs/_index/**`.

## 11. Change Process & Documentation Updates
**Rules**
- If changes touch manifest trigger paths, update affected AI_INDEX sections and source-of-truth specs first.
- New protocol fields or enums require updates in `docs/01_specs/**` before code changes merge.
- Keep section numbers stable; append new sections at the end.
**Checks**
- Review `docs/_index/ai_index_manifest.json` for trigger coverage.
- Include a change list and contract impact summary with each task.
**Scope**
- `docs/_index/**`, `docs/01_specs/**`, `backend/**`, `frontend/**`, `storage/**`.

## 12. Documentation Authority & Sync Obligations
**Rules**
- Authoritative docs: `docs/00_overview/**`, `docs/01_specs/**`, `docs/02_guides/**`.
- Human-only docs: `docs/99_human_only/**`. Do not cite or rely on these unless the task explicitly allows it.
- When a task explicitly requests an alignment report, write the report under `docs/99_human_only/alignment_reports/` using a dated filename (for example: `YYYY-MM-DD_<topic>_alignment_report.md`).
- Reference/legacy docs are non-authoritative; do not treat them as implementation truth.
- When modifying backend/frontend API routes, request/response fields, status codes, storage paths, JSON keys, enums, or settings keys/defaults/validation, you must update the matching docs.
- Every code commit touching those areas must include at least one docs update, or add a tracked entry to `docs/01_specs/TODO_DOCS_ALIGNMENT.md` explaining why the docs change is deferred.
- Frontend MVP now has panel-based pages (`frontend/play.html`, `frontend/debug.html`) using `styles.css` + JS modules (`api/store/panels/models/renderers`); legacy single-page console (`frontend/index.html` + `frontend/app.js`) remains for compatibility and scripted flow checks. Keep this aligned with `docs/02_guides/gameplay_flow.md`.
**Checks**
- Confirm updated docs cover API routes, storage layout, enums, and settings changes.
- If docs are deferred, ensure `docs/01_specs/TODO_DOCS_ALIGNMENT.md` contains a dated entry with evidence.
- For alignment tasks, confirm report output path is under `docs/99_human_only/alignment_reports/`.
- When changing gameplay flow UI controls or turn templates, run a manual chain check: create campaign -> world_generate -> map_generate -> actor_spawn -> move -> inventory_add -> chat/turn.
**Scope**
- `backend/**`, `frontend/**`, `docs/00_overview/**`, `docs/01_specs/**`, `docs/02_guides/**`, `docs/99_human_only/alignment_reports/**`, `docs/01_specs/TODO_DOCS_ALIGNMENT.md`.

## 13. CharacterFact Generation & Persistence
**Rules**
- Character generation outputs `CharacterFact` only; runtime authority remains `campaign.actors`.
- CharacterFact schema authority is `docs/01_specs/schemas/character_fact.v1.schema.json`.
- Prompt protocol authority is `docs/01_specs/prompts/character_fact_generate_v1.md`.
- Generated artifacts are temporary and must not change turn/tool contracts.
- Persist generated outputs under `storage/campaigns/<campaign_id>/characters/generated/` using batch + individual draft files.
- CharacterFact API endpoints are versioned under `/api/v1/campaigns/{campaign_id}/characters/...`.
- `request_id` must be unique per campaign (`409 Conflict` on duplicate submit).
- `__AUTO_ID__` must never be written to disk; allocate final IDs before writing batch/individual files.
**Checks**
- Verify generated payload excludes runtime fields (`position`, `hp`, `character_state`).
- Verify `meta` only uses predefined keys (`hooks`, `language`, `source`).
- Run generation/fact API tests when touching generation/reading logic.
**Scope**
- `backend/api/routes/characters.py`, `backend/app/character_fact_api_service.py`, `backend/app/character_fact_generation.py`, `backend/domain/character_fact_schema.py`, `backend/infra/character_fact_store.py`, `backend/infra/file_repo.py`, `backend/scripts/generate_character_facts.py`, `backend/domain/character_access.py`, `backend/tests/test_character_fact_api.py`, `backend/tests/test_character_fact_generation.py`, `docs/01_specs/character_fact_v1.md`, `docs/01_specs/storage_layout.md`, `docs/01_specs/schemas/character_fact.v1.schema.json`, `docs/01_specs/prompts/character_fact_generate_v1.md`.
