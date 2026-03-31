# AI_INDEX

Purpose: a stable, sectioned index of code constraints and verification points.
Use this as the default reference for every task.
External Resources Roadmap -> `docs/30_resources/external_resources_and_trace.md`

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
- `/api/v1/chat/turn` stable top-level response keys are `effective_actor_id`, `narrative_text`, `dialog_type`, `tool_calls`, `applied_actions`, `tool_feedback`, `conflict_report`, and `state_summary`.
- `/api/v1/chat/turn` omits top-level `debug` when trace is off; when trace is on, `debug.resources` is present and uses array categories.
- `/api/v1/chat/turn` keeps `tool_calls` / `applied_actions` as arrays; `tool_feedback` and `conflict_report` may be `null` depending on turn outcome.
- `/api/v1/chat/turn.state_summary` keeps stable v1 keys: `active_actor_id`, `positions`, `positions_parent`, `positions_child`, `hp`, `character_states`, `inventories`, `inventory_stack_ids`, `inventory_stacks`, `objective`, `active_area_id`, `active_area_name`, `active_area_description`, `active_actor_inventory`, `active_actor_inventory_stack_ids`, `active_actor_inventory_stacks`, `mistakes`, `consequences`, and `hostility`. Stack payloads are primary; aggregate inventory fields are derived compatibility snapshots.
- `GET /api/v1/campaign/get` returns the authoritative selected/actors/map/status snapshot for a valid campaign; `actors` exposes read-only actor runtime snapshot fields needed by Play refresh, including derived compatibility `inventory`, `inventory_stack_ids` exposes the stack-id companion view, `inventory_stacks` is the primary frontend inventory contract, `map.areas` exposes current reachability state, `status` carries lifecycle + milestone data from the same campaign snapshot, missing campaigns return `404`, and invalid persisted campaign payloads return `500` with a stable error detail.
- `GET /api/v1/map/view` returns area context plus `entities_in_area` built from current `campaign.entities` with an additive map-only projection of area-root item stacks from `campaign.items`, filtered to the actor's current area, with each entry's current `state`.
- `/api/v1/chat/turn` actor context resolution uses `execution.actor_id` first, then top-level `actor_id`, then `campaign.selected.active_actor_id`; response includes `effective_actor_id`.
- `/api/v1/chat/turn` accepts optional `context_hints.selected_stack_id` as the normal selection hint. `context_hints.selected_item_id` remains fallback-only compatibility for callers that cannot resolve a stack yet. Backend resolves selection against actor-owned stacks derived from `campaign.items` and injects `selected_item={id,stack_id,quantity,stack_quantity,label}` only when valid.
- When trace is enabled, `/api/v1/chat/turn.debug.selected_item` remains a minimal compatibility block, and `debug.selected_item_resolution` is the primary observability surface for stack/item selection resolution, including requested/resolved ids, status/reason, and light stack snapshot fields. Top-level `debug` remains omitted when trace is off.
- `/api/v1/chat/turn` runs under a per-campaign serial lock; concurrent same-campaign turns return `409`.
- `GET /api/v1/runtime/status` returns `ready` + `reason` for keyring/config readiness, and frontend play/debug uses it before sending turn requests.
- `POST /api/v1/runtime/unlock` is a local-only runtime unlock path used by `python -m backend.tools.unlock_keyring`; the frontend must not collect passphrases.
- `/api/v1/campaigns/{campaign_id}/world` resolves `campaign.selected.world_id` and returns world data; returns `409` when world_id is empty.
- Character Library REST is deterministic and separate from chat-turn tool flow:
  - `GET /api/v1/characters/library`
  - `GET /api/v1/characters/library/{character_id}`
  - `POST /api/v1/characters/library`
  - `POST /api/v1/campaigns/{campaign_id}/party/load`
  - `GET /api/v1/characters/library` must skip unreadable/invalid library files and still return valid entries
  - `GET /api/v1/characters/library/{character_id}` returns `404` for missing ids and `500` for invalid persisted library entries
  - `POST /api/v1/characters/library` rejects invalid request payloads with validation errors and must not overwrite an existing valid fact on failure
  - `POST /api/v1/campaigns/{campaign_id}/party/load` is idempotent for the same `campaign_id + character_id`: no duplicate party ids, no duplicate actor records, and no reset of actor runtime authority fields
  - repeated `party/load` may refresh canonical `meta.profile` fields from library data and backfill missing metadata, but must not overwrite `position`, `hp`, `character_state`, or `inventory`
- CharacterFact generate/read paths remain storage-authoritative draft artifacts only:
  - `POST /api/v1/campaigns/{campaign_id}/characters/generate` must not mutate `campaign.actors`, `selected.party_character_ids`, or `selected.active_actor_id`
  - duplicate CharacterFact `request_id` returns `409` without creating extra batch/draft files
  - `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches` must survive unreadable batch files
  - `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches/{request_id}` returns `404` for missing batches and `500` for invalid persisted batch files
  - `GET /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}` may fall back from unreadable draft to batch, returns `404` when missing, `500` when only an invalid draft exists, and `422` for schema-invalid fact payloads
  - `POST /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt` may update actor metadata/profile only; it must not overwrite actor `position`, `hp`, `character_state`, or `inventory`
  - adopt keeps accepted sidecar writes stable; missing facts return `404`, schema-invalid facts return `422`, and invalid accepted sidecars return `500`
- Changes to `Campaign`, `TurnLogEntry`, or API payloads must update `docs/01_specs/storage_layout.md` and `docs/20_runtime/testing/api_test_guide.md`.
**Checks**
- Run the API test guide for any changed endpoints.
- Compare JSON payloads against `backend/domain/models.py`.
**Scope**
- `backend/api/routes/**`, `backend/domain/models.py`, `docs/01_specs/storage_layout.md`, `docs/20_runtime/testing/api_test_guide.md`.

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
- `campaign.items` is the authoritative portable-item runtime store; `actors[*].inventory` is a derived compatibility view only.
- `Campaign.entities` is authoritative for scene object state and stable entity IDs.
- Portable items must not be created as authority-carrying entities; scene entities may still gate or expose interactions, but portable item persistence belongs in `campaign.items`.
- `move_options` is read-only and must not change positions or other state.
- Movement state changes require a `move` tool_call; narration alone does not change positions.
- Mainline portable-item acquisition uses `scene_action search` to reveal/discover and `scene_action take` to move ownership into actor-held stacks.
- `search` alone does not grant possession.
- `inventory_add` remains a bounded legacy-only contract for source-entity-backed inventory gain; narration alone still does not change inventory.
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
- Preferred local-first backend startup is `python scripts/run_backend.py` from the repo root because storage/config/secrets resolve under repo-root `storage/`.
- First-time local credential bootstrap may use `python -m backend.tools.setup_keyring`; unlock of an existing keyring remains `python -m backend.tools.unlock_keyring`.
- Backend startup runs a non-interactive LLM credential precheck only; passphrase entry happens via `python -m backend.tools.unlock_keyring`.
- Scenario-generated campaigns persist internal `scenario_runtime_fragment` authority for runtime gate/goal checks; scenario execution must not fall back to world metadata recovery logic.
- Campaign runtime state now also persists structured hostility/progression consequences under `campaign.hostility`; threshold-triggered outcomes must not exist only in narrative text.
- Storage fields match `docs/01_specs/storage_layout.md`.
- Portable items persist under `campaign.json.items`; inventory-only campaign seeds are unsupported.
- `docs/00_overview/PROJECT_STATUS.md` summarizes the current stable runtime/frontend/storage shape for Playable v1 handoff.
**Checks**
- Run the API test guide to verify files are written with expected shapes.
- Inspect storage files after changes to models or persistence logic.
**Scope**
- `backend/infra/file_repo.py`, `backend/services/llm_config.py`, `backend/services/keyring.py`, `backend/tools/setup_keyring.py`, `backend/tools/unlock_keyring.py`, `scripts/run_backend.py`, `storage/**`, `README.md`, `frontend/README_frontend.md`, `docs/01_specs/storage_layout.md`.

## 7. Map Data Integrity & Generation
**Rules**
- `reachable_area_ids` is authoritative; `map.connections` is derived and normalized.
- Map validation requires string reachable ids, no duplicates, no self loops, valid targets, and connected graphs per parent group.
- `map_generate` reverts on invalid maps and enforces `size` in `1..30`.
**Checks**
- Run `backend/tests/test_map_generate.py` and follow `docs/20_runtime/testing/map_generate_manual_test.md`.
- Review `backend/domain/map_models.py` for validation logic.
**Scope**
- `backend/domain/map_models.py`, `backend/app/tool_executor.py`, `docs/01_specs/storage_layout.md`, `docs/20_runtime/testing/map_generate_manual_test.md`.

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
- API contract changes require updating `docs/20_runtime/testing/api_test_guide.md`.
- Tool/state/map changes require running `backend/tests/test_map_generate.py`, `backend/tests/test_move_options.py`, and reviewing the manual map_generate guide when map logic changes.
- `world_generate` changes require running `backend/tests/test_world_generate_tool.py` and the local smoke script `scripts/smoke_world_generate.ps1` (guide: `docs/20_runtime/testing/world_generate_smoke_test.md`).
- Frontend gameplay flow UI/protocol changes require running `scripts/smoke_frontend_flow.ps1` and checking `frontend/README_frontend.md` + `docs/20_runtime/gameplay_flow.md` + `docs/20_runtime/frontend_entrypoints.md` for sync.
- Frontend readiness gating must not blank the page: base panels mount first, `not ready` is stored as state, and recovery works via polling or the minimal retry action.
- Frontend readiness polling must not churn focused input DOM; unchanged polling state should not trigger full input-panel re-render.
- Frontend `refreshCampaign` must only write state from a valid authoritative `campaign/get` payload; failed or invalid responses must leave existing party/active state untouched, clear stale campaign status display, avoid inventing a second map truth, and surface a handleable failure.
- Runtime unlock verification for local development uses `GET /api/v1/runtime/status` plus `python -m backend.tools.unlock_keyring`; startup `getpass()` prompts are no longer valid test expectations.
- For play-panel actor selection consistency changes, also run the manual guide `docs/20_runtime/testing/active_actor_integration_smoke.md`.
- For Play state convergence or refresh behavior changes, run `docs/20_runtime/testing/state_consistency_check.md`.
- For Playable v1 closure/regression handoff, run `docs/02_guides/testing/playable_v1_manual_test.md`.
- Release gate requires all three deterministic smoke scripts plus a recorded Set B 10-turn run from `docs/02_guides/testing/playable_v1_manual_test.md`.
- Play Action Planner supports structured envelopes (`move` / `scene_action`) and compiles one strict `UI_FLOW_STEP` per step.
- Round play delta contract is frontend-owned in `frontend/play.js` and must keep stable keys: `actor_id`, `changed`, `position`, `hp`, `character_state`, `inventory`, `error`.
- Spec changes in `docs/01_specs/**` must be reflected in this AI_INDEX.
**Checks**
- Run targeted tests and document results in the task output.
- Update `docs/_index/ai_index_manifest.json` if paths or sections change.
**Scope**
- `backend/tests/**`, `docs/20_runtime/testing/**`, `docs/01_specs/**`, `docs/_index/**`.

## 11. Change Process & Documentation Updates
**Rules**
- If changes touch manifest trigger paths, update affected AI_INDEX sections and source-of-truth specs first.
- New protocol fields or enums require updates in `docs/01_specs/**` before code changes merge.
- Use `docs/01_specs/DOC_SYNC_BASELINE.md` for the minimal Drive-sync checklist at milestone wrap-up.
- Keep section numbers stable; append new sections at the end.
**Checks**
- Review `docs/_index/ai_index_manifest.json` for trigger coverage.
- Include a change list and contract impact summary with each task.
**Scope**
- `docs/_index/**`, `docs/01_specs/**`, `backend/**`, `frontend/**`, `storage/**`.

## 12. Documentation Authority & Sync Obligations
**Rules**
- Local-first bootstrap docs live in `README.md` and `frontend/README_frontend.md`; keep these aligned with repo-root storage behavior, smoke-vs-real-run guidance, and runtime readiness flows.
- Authoritative docs: `docs/00_overview/**`, `docs/01_specs/**`, `docs/20_runtime/**`, `docs/30_resources/**`, `docs/90_playable/**`.
- Current active backlog lives in `docs/90_playable/PLAYABLE_V1_TODO.md`; completed baseline/closure status belongs in `docs/00_overview/PROJECT_STATUS.md`.
- Minimal sync baseline note: `docs/01_specs/DOC_SYNC_BASELINE.md`.
- Current architecture/status overview for Playable v1 lives in `docs/00_overview/PROJECT_STATUS.md`.
- Transitional exception: `docs/02_guides/testing/playable_v1_manual_test.md` remains as a stable manual-test entry path.
- Human-only docs: `docs/99_human_only/**`. Do not cite or rely on these unless the task explicitly allows it.
- Primary implementation lookup remains local (`backend/**`, `frontend/**`, `storage/**`, full docs tree). The ChatGPT web reference-doc package is lightweight context only and is not a substitute for local repo reading.
- The ChatGPT web reference-doc package must stay small and structure-oriented; do not expand it into a second full documentation mirror.
- Refresh `scripts/sync_chatgpt_docs.ps1` output at milestone or phase wrap-up when index/overview/status/roadmap/high-level architecture docs materially change. Do not treat Drive sync as required for every small doc edit.
- When a task explicitly requests an alignment report, write the report under `docs/99_human_only/alignment_reports/` using a dated filename (for example: `YYYY-MM-DD_<topic>_alignment_report.md`).
- Reference/legacy docs are non-authoritative; do not treat them as implementation truth.
- When modifying backend/frontend API routes, request/response fields, status codes, storage paths, JSON keys, enums, or settings keys/defaults/validation, you must update the matching docs.
- Every code commit touching those areas must include at least one docs update, or add a tracked entry to `docs/01_specs/TODO_DOCS_ALIGNMENT.md` explaining why the docs change is deferred.
- Frontend MVP uses panel-based pages (`frontend/play.html`, `frontend/debug.html`) with `styles.css` + JS modules (`api/store/panels/models/renderers`). `frontend/index.html` is a deprecated landing/redirect page to Play UI and must not execute legacy `app.js` flow.
**Checks**
- Confirm updated docs cover API routes, storage layout, enums, and settings changes.
- If docs are deferred, ensure `docs/01_specs/TODO_DOCS_ALIGNMENT.md` contains a dated entry with evidence.
- For alignment tasks, confirm report output path is under `docs/99_human_only/alignment_reports/`.
- When changing gameplay flow UI controls or turn templates, run a manual chain check: create campaign -> world_generate -> map_generate -> actor_spawn -> move -> inventory_add -> chat/turn.
- At stage closure, if the lightweight ChatGPT reference set changed materially, refresh the Drive package with `scripts/sync_chatgpt_docs.ps1`.
**Scope**
- `README.md`, `frontend/README_frontend.md`, `backend/**`, `frontend/**`, `docs/00_overview/**`, `docs/01_specs/**`, `docs/20_runtime/**`, `docs/30_resources/**`, `docs/90_playable/**`, `docs/99_human_only/alignment_reports/**`, `docs/01_specs/TODO_DOCS_ALIGNMENT.md`.

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

## 14. Formal Gameplay Model & Alignment System
**Rules**
- Formal Gameplay Model is a read-only design-time and validation-time layer only.
- It currently covers generated scenarios plus the preset adapter path for `test_watchtower_world` and `midnight_archive_world`.
- Authoritative goal state lives in `Goal(...)`; goal nodes are optional and non-authoritative.
- `dependency_groups` is active in current validation logic and supports `all_of` and `any_of`.
- Current formal validation includes structural solvability plus `multi_path_coverage` and `clue_support_coverage`.
- Current quality/audit outputs include `gate_quality_statuses`, `overall_quality_status`, gate/overall authoring audit, preset alignment audit, and preset remediation backlog output.
- Generator-side shaping annotations currently include `gate_clue` and `gate_clue_support_gap`.
- Current preset semantics are intentionally narrow:
  - `midnight_archive_world` is the current `partial` single-route sample
  - `test_watchtower_world` remains the `legacy` baseline
  - trusted `aligned` state now also requires full mapped preset-area coverage for the current adapter scope
- Current preset remediation backlog output also includes `limited_preset_coverage_alignment` for route-limited samples that expose modern signals but not full preset coverage.
- Formal validation must not change turn execution, tool execution, inventory, or goal completion timing.
**Checks**
- Run `backend/tests/test_formal_gameplay_v0.py` for generator-path validation coverage.
- Run `backend/tests/test_formal_gameplay_v1.py` for dependency-group, multi-path, clue-support, quality, and authoring-audit coverage.
- Run `backend/tests/test_formal_preset_adapter.py` for preset-path mapping, alignment audit, and backlog coverage.
- Keep `docs/01_specs/formal_gameplay_model_v0.md` aligned with current implementation truth, especially current Midnight Archive limitations and read-only boundaries.
**Scope**
- `backend/domain/formal_gameplay_model.py`, `backend/app/formal_mapper.py`, `backend/app/formal_preset_mapper.py`, `backend/app/formal_validator.py`, `backend/app/formal_preset_alignment_audit.py`, `backend/app/formal_preset_alignment_backlog.py`, `backend/app/scenario_bridge.py`, `backend/domain/scenario_bridge_models.py`, `backend/app/world_presets.py`, `backend/tests/test_formal_gameplay_v0.py`, `backend/tests/test_formal_gameplay_v1.py`, `backend/tests/test_formal_preset_adapter.py`, `docs/01_specs/formal_gameplay_model_v0.md`.

## 15. Scenario Gameplay Validation & Runtime Consequences
**Rules**
- Scenario generation uses the existing `backend/app/scenario_builder.py -> backend/app/scenario_validator.py` chain for gameplay validation; invalid generated scenarios must fail before bootstrap/runtime.
- Current generation-time gameplay validation covers:
  - reachable completion path
  - satisfiable gate dependency placement
  - obvious dead-end rejection
  - critical clue existence, reachability before the dependency point, and valid clue/item/entity binding
- Current runtime consequence loop remains system-controlled and stateful:
  - per-entity hostility accumulates from structured hostile `scene_action` inputs
  - threshold crossing triggers `interaction_locked`
  - assaultive NPC `talk` can trigger one-shot `combat_resolved` with deterministic `player_repelled` or opt-in `npc_disabled` aftermaths
  - the current recommended authoring shape for searchable aftermaths is `combat_aftermath_hook={"kind":"search_loot","item_id":"...","item_label":"..."}` on the target NPC
  - selected `npc_disabled` aftermaths can use that hook and feed back into the existing `search -> reveal -> take` path
  - legacy `combat_reveal_item_id` / `combat_reveal_item_label` inputs still normalize into that same searchable-aftermath contract for compatibility
  - locking the critical reveal source in the current key-gate scenario can trigger `progression_locked`, fail the goal, and end the campaign lifecycle
- These checks/outcomes must not rely on LLM narrative inference, fallback recovery, or a second runtime authority model.
**Checks**
- Run `backend/tests/test_scenario_builder.py` and `backend/tests/test_scenario_templates.py` for generation-time validation coverage.
- Run `backend/tests/test_scene_action_tool.py`, `backend/tests/test_turn_hostility_thresholds.py`, `backend/tests/test_turn_progression_coupling.py`, and `backend/tests/test_turn_response_contract_api.py` for runtime hostility/progression/combat coverage.
- Keep `README.md`, `docs/00_overview/README.md`, and `docs/00_overview/PROJECT_STATUS.md` aligned with the current runtime authority and gameplay validation boundaries.
**Scope**
- `backend/app/scenario_builder.py`, `backend/app/scenario_validator.py`, `backend/app/campaign_hostility_service.py`, `backend/app/tool_executor.py`, `backend/app/turn_service.py`, `backend/domain/models.py`, `backend/tests/test_scene_action_tool.py`, `backend/tests/test_scenario_builder.py`, `backend/tests/test_scenario_templates.py`, `backend/tests/test_turn_hostility_thresholds.py`, `backend/tests/test_turn_progression_coupling.py`, `backend/tests/test_turn_response_contract_api.py`, `README.md`, `docs/00_overview/README.md`, `docs/00_overview/PROJECT_STATUS.md`, `docs/20_runtime/gameplay_flow.md`.
