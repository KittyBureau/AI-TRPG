# PLAYABLE v1 TODO (Development Mainline)

Last updated: 2026-03-06

## Positioning

This document is the **only development-driving TODO** for Playable v1.

- `PLAYABLE_V1_TODO.md`: mainline execution board.
- Older TODO files (including legacy/archive/design TODOs): reference/history only.

## Scope and Non-goals

Playable v1 target: complete a stable loop from campaign creation to repeatable multi-turn play with deterministic regression coverage.

Non-goals for Playable v1:

- battle system overhaul
- advanced NPC AI planner
- economy simulation
- skill tree/progression system

## Execution Rhythm (Mandatory)

1. Pick only 1-2 P0 items at a time.
2. Implement minimal change.
3. Run targeted tests and smoke checks until green.
4. Update this TODO item status.
5. Repeat.

## Status Legend

- `TODO`: not started
- `WIP`: in progress
- `DONE`: completed and verified

## Item Counts

- P0: 14 items (must-complete)
- P1: 13 items
- P2: 11 items
- Total: 38 items

## TOC

- [P0 (Must Complete)](#p0-must-complete)
- [P1 (Important, Not Blocking v1 Launch)](#p1-important-not-blocking-v1-launch)
- [P2 (Post-v1 / Optimization)](#p2-post-v1--optimization)

---

## P0 (Must Complete)

### P0-01 Turn response contract freeze
- Status: `DONE`
- Why: play loop depends on stable response fields.
- Scope: `backend/api/routes/chat.py`, `backend/app/turn_service.py`, `backend/domain/models.py`
- Acceptance: `/api/v1/chat/turn` keeps required keys and compatible semantics.
- Tests: `backend/tests/test_api_v1_routing.py`, `scripts/smoke_full_gameplay.ps1`
- Verification Evidence:
  - `pytest -q` -> `154 passed`
  - `pytest -q backend/tests/test_turn_response_contract_api.py backend/tests/test_trace_gate_api.py backend/tests/test_sample_playthrough_v0.py` -> `7 passed`
  - `backend/tests/test_turn_response_contract_api.py` freezes narrative-only success, mixed tool success+failure, conflict retry exhaustion response, trace-on debug resources, and turn_log alignment
  - `backend/tests/test_trace_gate_api.py` keeps `debug` omitted when trace is off and `debug.resources` array categories when trace is on
  - Docs synced to current runtime contract: `docs/01_specs/storage_layout.md`, `docs/20_runtime/testing/api_test_guide.md`, `docs/20_runtime/gameplay_flow.md`, `docs/_index/AI_INDEX.md`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
- Rollback: revert turn response contract changes and restore previous API shape.

### P0-02 Effective actor resolution hardening
- Status: `DONE`
- Why: wrong actor execution breaks state trust.
- Scope: `backend/api/routes/chat.py`, `backend/app/turn_service.py`, `backend/app/tool_executor.py`
- Acceptance: priority `execution.actor_id -> actor_id -> selected.active_actor_id` is stable.
- Tests: `backend/tests/test_turn_execution_actor_context.py`, `backend/tests/test_select_actor_validation.py`
- Verification Evidence:
  - `pytest -q` -> `117 passed`
  - `backend/tests/test_turn_execution_actor_context.py` covers `execution.actor_id -> actor_id -> selected.active_actor_id`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
- Rollback: restore previous actor resolution path and mismatch rejection logic.

### P0-03 Actor mismatch rejection reliability
- Status: `DONE`
- Why: prevents cross-actor unintended mutations.
- Scope: `backend/app/tool_executor.py`, `backend/app/turn_service.py`
- Acceptance: mismatched `args.actor_id` always yields `actor_context_mismatch`.
- Tests: `backend/tests/test_turn_execution_actor_context.py`, manual Set B in `docs/02_guides/testing/playable_v1_manual_test.md`
- Verification Evidence:
  - `pytest -q` -> `117 passed`
  - `backend/tests/test_turn_execution_actor_context.py` asserts mismatched `move` and `inventory_add` both return `failed_calls.status == "rejected"` and `reason == "actor_context_mismatch"`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
- Rollback: revert strict mismatch guard to last green state.

### P0-04 Campaign turn lock reliability
- Status: `DONE`
- Why: concurrent writes can corrupt campaign state.
- Scope: `backend/app/turn_service.py`
- Acceptance: same-campaign concurrent turn returns deterministic `409` behavior.
- Tests: `backend/tests/test_turn_campaign_lock.py`
- Verification Evidence:
  - `pytest -q` -> `121 passed`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
  - `backend/tests/test_turn_campaign_lock.py` covers same-campaign `409 turn_in_progress`, different-campaign concurrent success, and lock release after turn exception
- Rollback: restore previous lock registry and error mapping.

### P0-05 World generate deterministic safety
- Status: `DONE`
- Why: world bootstrap must be reproducible and recoverable.
- Scope: `backend/app/world_service.py`, `backend/infra/file_repo.py`, `backend/app/tool_executor.py`
- Acceptance: bound world id reuse, deterministic world stub behavior, no drift on repeated call.
- Tests: `backend/tests/test_world_generate_tool.py`, `scripts/smoke_world_generate.ps1`
- Verification Evidence:
  - `pytest -q` -> `146 passed`
  - `backend/tests/test_world_repo.py::test_get_or_create_world_stub_is_deterministic_across_storage_roots`
  - `backend/tests/test_world_generate_tool.py::test_world_generate_stub_repeated_calls_keep_world_json_stable`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1` -> `PASS (A/B/C/D)`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1 -KeepWorkspace` -> `PASS (8/8)`
- Rollback: revert world generate path and file repo changes.

### P0-06 Map generate authority integrity
- Status: `DONE`
- Why: broken map graph blocks movement loop.
- Scope: `backend/domain/map_models.py`, `backend/app/tool_executor.py`
- Acceptance: `reachable_area_ids` authority, map validation and revert-on-invalid remain intact.
- Tests: `backend/tests/test_map_generate.py`, `docs/20_runtime/testing/map_generate_manual_test.md`
- Verification Evidence:
  - `pytest -q` -> `146 passed`
  - `backend/tests/test_map_generate.py::test_map_generate_updates_only_map_authority`
  - `backend/tests/test_map_generate.py::test_map_generate_invalid_graph_rolls_back_state`
  - `backend/tests/test_map_generate.py::test_map_generate_exception_rolls_back_state`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1 -KeepWorkspace` -> `PASS (8/8)`
- Rollback: revert map validation and normalization changes.

### P0-07 Move and move_options closure
- Status: `DONE`
- Why: exploration loop needs deterministic movement affordances.
- Scope: `backend/app/tool_executor.py`, `backend/app/turn_service.py`
- Acceptance: `move_options` is read-only; `move` is required for location changes.
- Tests: `backend/tests/test_move.py`, `backend/tests/test_move_options.py`, `scripts/smoke_full_gameplay.ps1`
- Verification Evidence:
  - `pytest -q` -> `149 passed`
  - `pytest -q backend/tests/test_move.py backend/tests/test_move_options.py backend/tests/test_scene_action_tool.py backend/tests/test_scene_action_turn_api.py` -> `21 passed`
  - `backend/tests/test_move_options.py::test_move_options_is_read_only_for_persistent_state`
  - `backend/tests/test_scene_action_turn_api.py::test_chat_turn_without_tools_does_not_change_actor_position`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
  - Modified tests: `backend/tests/test_move_options.py`, `backend/tests/test_scene_action_turn_api.py`
- Rollback: restore previous move/move_options execution behavior.

### P0-08 Scene interaction minimum viable path
- Status: `DONE`
- Why: non-move interactions are core to playability.
- Scope: `backend/app/tool_executor.py`, `backend/tests/test_scene_action_tool.py`
- Acceptance: one valid `scene_action` path works end-to-end and persists entity deltas.
- Tests: `backend/tests/test_scene_action_tool.py`, `backend/tests/test_scene_action_turn_api.py`
- Verification Evidence:
  - `pytest -q` -> `149 passed`
  - `pytest -q backend/tests/test_move.py backend/tests/test_move_options.py backend/tests/test_scene_action_tool.py backend/tests/test_scene_action_turn_api.py` -> `21 passed`
  - `backend/tests/test_scene_action_tool.py::test_scene_action_exception_rolls_back_entity_changes`
  - `backend/tests/test_scene_action_turn_api.py::test_chat_turn_scene_action_updates_campaign_entities`
  - API path verified via turn test: `scene_action=open` writes `campaign.json.entities.crate_01.state.opened=true` while `actors.pc_001.position` remains unchanged
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
  - Modified tests: `backend/tests/test_scene_action_tool.py`, `backend/tests/test_scene_action_turn_api.py`
- Rollback: revert scene_action mutation path to last green commit.

### P0-09 Inventory mutation authority
- Status: `DONE`
- Why: loot progression needs durable state mutation.
- Scope: `backend/app/tool_executor.py`, `backend/domain/models.py`
- Acceptance: inventory changes persist only via `inventory_add` tool and appear in state summary.
- Tests: `backend/tests/test_inventory_add_tool.py`, `scripts/smoke_full_gameplay.ps1`
- Verification Evidence:
  - `pytest -q` -> `150 passed`
  - `pytest -q backend/tests/test_inventory_add_tool.py backend/tests/test_move.py backend/tests/test_scene_action_tool.py` -> `22 passed`
  - `backend/tests/test_inventory_add_tool.py::test_inventory_add_applies_and_updates_actor_inventory`
  - `backend/tests/test_inventory_add_tool.py::test_regular_turn_does_not_change_inventory_without_inventory_add`
  - `backend/tests/test_move.py::test_move_succeeds_with_explicit_actor_id`
  - `backend/tests/test_scene_action_tool.py::test_scene_action_take_and_drop_updates_location`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
  - Modified tests: `backend/tests/test_inventory_add_tool.py`, `backend/tests/test_move.py`, `backend/tests/test_scene_action_tool.py`
- Rollback: revert inventory mutation handling.

### P0-10 Storage authority consistency
- Status: `DONE`
- Why: runtime needs one source of truth for actor state.
- Scope: `backend/infra/file_repo.py`, `backend/domain/character_access.py`, `backend/domain/models.py`
- Acceptance: `actors[*]` remains authoritative; legacy mirrors are compatibility-only.
- Tests: `backend/tests/test_turn_service_state_snapshot.py`, `backend/tests/test_character_facade.py`
- Verification Evidence:
  - `pytest -q` -> `121 passed`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
  - `backend/tests/test_character_facade.py`, `backend/tests/test_turn_service_state_snapshot.py`, `backend/tests/test_move.py`, and `backend/tests/test_inventory_add_tool.py` verify reads may use legacy mirrors, but runtime updates/persistence only write `actors[*]` and saved mirror fields remain empty
- Rollback: restore previous migration/legacy mirror handling.

### P0-11 Trace gate default-off safety
- Status: `DONE`
- Why: debug payload overhead should be opt-in.
- Scope: `backend/domain/settings.py`, `backend/app/turn_service.py`, `backend/app/debug_resources.py`
- Acceptance: `debug` absent by default; appears only when trace enabled.
- Tests: `backend/tests/test_turn_service_lifecycle.py`, `docs/20_runtime/testing/api_test_guide.md`
- Verification Evidence:
  - `pytest -q` -> `141 passed`
  - `backend/tests/test_trace_gate_api.py::test_chat_turn_omits_top_level_debug_when_trace_is_off`
  - `backend/tests/test_trace_gate_api.py::test_settings_apply_toggles_trace_and_chat_turn_debug_contract`
  - API trace gate checks are covered by the tests above: trace off omits top-level `debug`; trace on includes `debug.resources` with array categories and legacy debug compatibility fields
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
- Rollback: revert debug payload gating logic.

### P0-12 External resource fallback safety
- Status: `DONE`
- Why: resource file/manifest errors must degrade gracefully.
- Scope: `backend/infra/resource_loader.py`, `resources/manifest.json`
- Acceptance: prompt/flow/schema/template strict loader + policy fallback behavior remains stable.
- Tests: `backend/tests/test_policy_resource_loader.py`, `backend/tests/test_resources_manifest_hashes.py`
- Verification Evidence:
  - `pytest -q` -> `141 passed`
  - `backend/tests/test_policy_resource_loader.py` covers policy fallback for manifest missing, section/name missing, invalid entry shape, multiple enabled, missing file, invalid JSON, and invalid content
  - `backend/tests/test_resource_loader_strict.py` keeps prompt/flow/schema/template loaders strict and verifies hash mismatch alone does not block loading
  - `backend/tests/test_turn_service_lifecycle.py::test_turn_profile_trace_policy_fallback_keeps_turn_runtime_stable` verifies malformed external policy falls back to builtin without turn failure
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
- Rollback: restore previous loader fallback behavior.

### P0-13 Frontend panel loop stability
- Status: `DONE`
- Why: playable loop must function from Play UI without raw JSON edits.
- Scope: `frontend/play.js`, `frontend/store/store.js`, `frontend/panels/*.js`, `frontend/api/api.js`
- Acceptance: campaign -> party -> active actor -> turn path is repeatable in Play UI.
- Tests: `scripts/smoke_frontend_flow.ps1`, `docs/20_runtime/testing/active_actor_integration_smoke.md`
- Verification Evidence:
  - `pytest -q` -> `150 passed`
  - `node --experimental-default-type=module --test frontend/tests/store_loop.test.mjs` -> `3 passed`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1` -> `PASS (8/8)`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
  - `frontend/tests/store_loop.test.mjs` verifies `refreshCampaign`, `selectActiveActor`, and `recordTurnResult` keep active actor / applied actions synchronized in store
  - Modified tests: `frontend/tests/store_loop.test.mjs`, `scripts/smoke_frontend_flow.ps1`
- Rollback: revert Play panel/store changes as one unit.

### P0-14 Release gate: deterministic suite + 10-turn manual
- Status: `DONE`
- Why: Playable v1 must be provably reproducible.
- Scope: `scripts/smoke_world_generate.ps1`, `scripts/smoke_full_gameplay.ps1`, `scripts/smoke_frontend_flow.ps1`, `docs/02_guides/testing/playable_v1_manual_test.md`
- Acceptance: all deterministic smokes pass and manual 10-turn checklist passes.
- Tests: all three smoke scripts + Set B manual run
- Verification Evidence:
  - `pytest -q` -> `154 passed`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1` -> `PASS (A/B/C/D)`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1` -> `PASS (8/8)`
  - `powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1` -> `PASS (8/8)`
  - Set B run record captured at `.tmp/manual_set_b_release/20260306T_set_b/set_b_record.json`
  - Set B summary: trace-off PASS, trace-on PASS, 10 turns completed, observed `world_generate/map_generate/actor_spawn/move_options/scene_action/move/inventory_add/narrative-only`, `turn_log.jsonl == 10`, storage parseable PASS, actor authority coherent PASS
  - Manual recording template added to `docs/02_guides/testing/playable_v1_manual_test.md`; release-gate cleanup stability hardened in `scripts/smoke_full_gameplay.ps1`
- Rollback: block release and revert last unstable changeset.

---

## P1 (Important, Not Blocking v1 Launch)

### P1-01 Campaign status and milestone UX alignment
- Status: `TODO`
- Why: lifecycle observability helps run stability.
- Scope: `backend/api/routes/campaign.py`, `frontend/panels/campaign_panel.js`
- Acceptance: status/milestone endpoints are visible and consistent in UI/API.
- Tests: `backend/tests/test_campaign_observability_api.py`, manual Play panel check
- Rollback: disable new UI wiring and keep API baseline.

### P1-02 Campaign get endpoint robustness
- Status: `TODO`
- Why: frontend refresh depends on authoritative campaign read.
- Scope: `backend/api/routes/campaign.py`, `frontend/store/store.js`
- Acceptance: refresh path handles missing/invalid campaigns predictably.
- Tests: `backend/tests/test_campaign_get_endpoint.py`, `docs/20_runtime/testing/state_consistency_check.md`
- Rollback: revert refresh integration.

### P1-03 Map view scene entities consistency
- Status: `TODO`
- Why: scene interaction depends on area-local entity visibility.
- Scope: `backend/api/routes/map.py`, `backend/app/turn_service.py`
- Acceptance: `GET /map/view` entity list matches campaign entity state.
- Tests: `backend/tests/test_map_view_scene_entities.py`
- Rollback: restore previous map view payload builder.

### P1-04 Character library robustness hardening
- Status: `TODO`
- Why: party bootstrapping should survive partial bad data.
- Scope: `backend/app/character_library_service.py`, `backend/api/routes/character_library.py`
- Acceptance: list/get/upsert handle malformed entries safely.
- Tests: `backend/tests/test_character_library_api.py`
- Rollback: revert stricter normalization/validation logic.

### P1-05 Party load idempotency and metadata rules
- Status: `TODO`
- Why: repeated load should not duplicate or corrupt party state.
- Scope: `backend/app/party_load_service.py`, `backend/api/routes/character_library.py`
- Acceptance: repeated party load is idempotent and profile write behavior remains stable.
- Tests: `backend/tests/test_character_library_api.py`, `backend/tests/test_campaign_get_endpoint.py`
- Rollback: restore previous party load path.

### P1-06 Character fact generate flow reliability
- Status: `TODO`
- Why: generated facts support rapid playable setup.
- Scope: `backend/app/character_fact_generation.py`, `backend/app/character_fact_api_service.py`
- Acceptance: generate/list/get paths remain deterministic in file outputs and errors.
- Tests: `backend/tests/test_character_fact_api.py`, `backend/tests/test_character_fact_generation.py`
- Rollback: revert generation API changes.

### P1-07 Character fact adopt safety
- Status: `TODO`
- Why: adopting facts must not break runtime actor authority.
- Scope: `backend/app/character_fact_api_service.py`, `backend/domain/character_access.py`
- Acceptance: adoption updates profile metadata without changing actor runtime authority fields.
- Tests: `backend/tests/test_character_fact_api.py`, `backend/tests/test_character_facade.py`
- Rollback: restore previous adoption merge logic.

### P1-08 Conflict detector false-positive reduction
- Status: `TODO`
- Why: unnecessary retries degrade user experience.
- Scope: `backend/app/conflict_detector.py`, `backend/app/turn_service.py`
- Acceptance: no increase in false conflict blocks on stable smoke scenarios.
- Tests: `backend/tests/test_chat_semantic_guard.py`, `scripts/smoke_full_gameplay.ps1`
- Rollback: revert detector heuristic changes.

### P1-09 Prompt context payload hygiene
- Status: `TODO`
- Why: reduce token waste and metadata leakage.
- Scope: `backend/app/turn_service.py`
- Acceptance: adopted profile usage remains intact while actor meta redundancy is controlled.
- Tests: `backend/tests/test_turn_service_lifecycle.py`
- Rollback: restore previous prompt context assembly.

### P1-10 Frontend debug resources rendering parity
- Status: `TODO`
- Why: troubleshooting requires stable debug visual contract.
- Scope: `frontend/utils/debug_resources.js`, `frontend/debug.js`
- Acceptance: debug page can render both `debug.resources` and legacy debug fields consistently.
- Tests: manual debug page check + targeted API trace checks
- Rollback: revert debug renderer changes.

### P1-11 Smoke script diagnostics quality
- Status: `TODO`
- Why: fast failure localization reduces fix time.
- Scope: `scripts/smoke_full_gameplay.ps1`, `scripts/smoke_frontend_flow.ps1`, `scripts/smoke_world_generate.ps1`
- Acceptance: script failures report actionable location/field details.
- Tests: controlled negative runs + rerun smoke scripts
- Rollback: restore prior smoke scripts.

### P1-12 Docs sync gate discipline
- Status: `TODO`
- Why: keep docs aligned with runtime behavior across iterations.
- Scope: `docs/_index/AI_INDEX.md`, `docs/_index/ai_index_manifest.json`, `docs/01_specs/TODO_DOCS_ALIGNMENT.md`
- Acceptance: any contract-impacting changes include docs update or TODO defer record.
- Tests: review checklist + path consistency scan in `docs/00_overview/DOCS_PATH_MAPPING.md`
- Rollback: revert docs gating edits and restore previous manifest/index mapping.

### P1-13 Preparation for Future Context System
- Status: `TODO`
- Why: prepare data shape and observability for future context optimization without changing current runtime behavior.
- Scope: future data model hooks and prompt trace observability only; no current prompt builder changes.
- Tasks:
  - Allow entities/areas to optionally contain a lightweight `tags` field (unused for now).
  - Ensure debug trace records prompt token counts.
  - Do not change current prompt building logic yet.
- Status Note: Preparation only. No runtime changes.
- Acceptance: prep work is limited to optional schema/documentation/trace readiness and preserves current prompt assembly behavior.
- Tests: docs review only until implementation is explicitly scheduled.
- Rollback: remove unused prep hooks and trace notes if they create confusion before implementation.

---

## P2 (Post-v1 / Optimization)

### P2-01 Additional world generator variants
- Status: `TODO`
- Why: enrich content variety without blocking v1 loop.
- Scope: `backend/domain/world_models.py`, `backend/infra/file_repo.py`
- Acceptance: optional generator variants keep world contract unchanged.
- Tests: `backend/tests/test_world_api.py`, `backend/tests/test_world_generate_tool.py`
- Rollback: disable variant selection and keep stub generator.

### P2-02 Tool policy schema tightening
- Status: `TODO`
- Why: explicit policy schema lowers config ambiguity.
- Scope: `resources/policies/tool_policy_v1.json`, `backend/infra/resource_loader.py`
- Acceptance: policy metadata validation improves without changing runtime fallback safety.
- Tests: `backend/tests/test_policy_resource_loader.py`
- Rollback: revert strict policy schema enforcement.

### P2-03 Extended debug resource metadata
- Status: `TODO`
- Why: deeper observability for production diagnostics.
- Scope: `backend/app/turn_service.py`, `backend/app/debug_resources.py`, `resources/schemas/debug_resources_v1.schema.json`
- Acceptance: added metadata remains backward compatible with current UI parser.
- Tests: `backend/tests/test_debug_resources_contract_schema.py`, manual debug page check
- Rollback: revert extra debug fields.

### P2-04 Frontend offline trace bundle improvements
- Status: `TODO`
- Why: improve bug report reproducibility.
- Scope: `frontend/debug.js`, `frontend/models/log_entry.js`
- Acceptance: exported bundle contains sufficient replay context without backend changes.
- Tests: manual debug export/import review
- Rollback: restore previous export format.

### P2-05 Map generation tuning knobs
- Status: `TODO`
- Why: more controllable content scale for long sessions.
- Scope: `backend/app/tool_executor.py`, `backend/domain/map_models.py`
- Acceptance: optional constraints remain bounded and validated.
- Tests: `backend/tests/test_map_generate.py`, manual map smoke
- Rollback: remove new knobs and keep baseline constraints.

### P2-06 Character fact draft UX improvements
- Status: `TODO`
- Why: human review/adopt loop can be faster.
- Scope: `backend/app/character_fact_api_service.py`, `frontend/panels/character_library_panel.js`
- Acceptance: review/adopt actions are easier without contract break.
- Tests: `backend/tests/test_character_fact_api.py`, manual Play panel verification
- Rollback: restore previous draft/adopt UI behavior.

### P2-07 Campaign lifecycle summary UX
- Status: `TODO`
- Why: end-state reasoning and restart actions become clearer.
- Scope: `backend/api/routes/campaign.py`, `frontend/panels/campaign_panel.js`
- Acceptance: lifecycle reason and milestone summary are visible and accurate.
- Tests: `backend/tests/test_campaign_observability_api.py`, manual UI status check
- Rollback: revert lifecycle UI extension.

### P2-08 Docs link checker automation
- Status: `TODO`
- Why: prevent future path drift after reorg.
- Scope: `docs/00_overview/DOCS_PATH_MAPPING.md` process, optional CI script in docs tooling
- Acceptance: one-command broken-path scan is repeatable in contributor workflow.
- Tests: run scan method and verify no entry-doc failures
- Rollback: disable automation and keep manual scan instructions.

### P2-09 Additional frontend smoke scenarios
- Status: `TODO`
- Why: improve coverage for edge UI sequencing.
- Scope: `scripts/smoke_frontend_flow.ps1`, `docs/20_runtime/testing/active_actor_integration_smoke.md`
- Acceptance: extra scenarios do not destabilize baseline smoke runtime.
- Tests: frontend smoke script reruns with scenario variants
- Rollback: keep minimal baseline smoke path only.

### P2-10 Resource version switch rehearsal playbook
- Status: `TODO`
- Why: lower risk for prompt/flow/schema/policy version operations.
- Scope: `resources/README.md`, `resources/CHANGELOG.md`, `docs/30_resources/external_resources_and_trace.md`
- Acceptance: documented switch + rollback drill is repeatable by non-authors.
- Tests: manual manifest toggle rehearsal + `pytest -q`
- Rollback: revert manifest toggle and changelog entry per playbook.

### P2-11 Context Architecture Optimization (Queued)
- Status: `TODO`
- STATUS: queued for P2 (not implemented).
- Why: future improvement to support long play sessions with stable world consistency and lower token usage.
- Core idea:
  - Build prompts from **state + area context** instead of long dialogue history.
  - Current area: full description + entity tags.
  - Nearby areas: summarized state.
  - Distant world: compressed world facts.
  - Recent dialogue: short rolling window only.
- Subtasks:
  - Implement a **Context Builder** module responsible for constructing prompts.
  - Introduce **persistent tags** and **transient tags (TTL)** for entities and areas.
  - Replace long dialogue history with **state-derived summaries**.
  - Add token monitoring and heuristics to trigger compression.
- Acceptance: design and implementation, when scheduled, preserve world consistency while reducing token growth in long sessions.
- Tests: future long-session regression coverage and prompt-size observability checks after implementation is approved.
- Rollback: keep the current history-oriented prompt assembly if the optimization proves unstable.
