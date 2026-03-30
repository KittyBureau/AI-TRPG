# PLAYABLE v1 TODO (Active Backlog)

Last updated: 2026-03-30

## Positioning

This file now keeps only real unfinished work.

- Completed baseline and closure status lives in `docs/00_overview/PROJECT_STATUS.md`.
- Historical round-by-round notes remain reference-only.
- Add new backlog items here only when they are still actionable.

## Status Legend

- `TODO`: not started
- `WIP`: in progress

## Active P1 Polish

### P1-20 Actor initial-position closure for loaded/null-position actors
- Status: `TODO`
- Why: loaded or newly adopted actors with missing position still need one explicit runtime policy.
- Scope: `backend/api/routes/characters.py`, `backend/app/turn_service.py`, `frontend/store/store.js`, related actor bootstrap tests.
- Acceptance: active actors in the normal Play flow either receive a stable initial position or expose one deterministic fallback policy without inventing frontend map state.
- Tests: `backend/tests/test_character_library_api.py`, `frontend/tests/store_loop.test.mjs`, targeted Play refresh smoke.

### P1-21 Minimal current-turn result visibility cleanup
- Status: `TODO`
- Why: current-turn applied actions/tool feedback are available but not always surfaced coherently in the Play flow.
- Scope: `frontend/play.js`, `frontend/panels/debug_panel.js`, minimal supporting docs/tests.
- Acceptance: current-turn result visibility is coherent in the active Play flow without inventing a second state source.
- Tests: `frontend/tests/store_loop.test.mjs`, targeted Play smoke/manual check.

## Active P2 Tracks

### P2-02 Tool policy schema tightening
- Status: `TODO`
- Why: explicit policy schema lowers config ambiguity.
- Scope: `resources/policies/tool_policy_v1.json`, `backend/infra/resource_loader.py`
- Tests: `backend/tests/test_policy_resource_loader.py`

### P2-03 Extended debug resource metadata
- Status: `TODO`
- Why: deeper observability for production diagnostics.
- Scope: `backend/app/turn_service.py`, `backend/app/debug_resources.py`, `resources/schemas/debug_resources_v1.schema.json`
- Tests: `backend/tests/test_debug_resources_contract_schema.py`, manual debug page check.

### P2-04 Frontend offline trace bundle improvements
- Status: `TODO`
- Why: improve bug report reproducibility.
- Scope: `frontend/debug.js`, `frontend/models/log_entry.js`
- Tests: manual debug export/import review.

### P2-05 Map generation tuning knobs
- Status: `TODO`
- Why: more controllable content scale for long sessions.
- Scope: `backend/app/tool_executor.py`, `backend/domain/map_models.py`
- Tests: `backend/tests/test_map_generate.py`, manual map smoke.

### P2-06 Character fact draft UX improvements
- Status: `TODO`
- Why: human review/adopt loop can be faster.
- Scope: `backend/app/character_fact_api_service.py`, `frontend/panels/character_library_panel.js`
- Tests: `backend/tests/test_character_fact_api.py`, manual Play panel verification.

### P2-07 Campaign lifecycle summary UX
- Status: `TODO`
- Why: end-state reasoning and restart actions should become clearer now that runtime can end in structured failure.
- Scope: `backend/api/routes/campaign.py`, `frontend/panels/campaign_panel.js`
- Tests: `backend/tests/test_campaign_observability_api.py`, manual UI status check.

### P2-08 Docs link checker automation
- Status: `TODO`
- Why: prevent future path drift after reorg.
- Scope: docs tooling and contributor workflow.
- Tests: one-command scan with no entry-doc failures.

### P2-09 Additional frontend smoke scenarios
- Status: `TODO`
- Why: improve coverage for edge UI sequencing.
- Scope: `scripts/smoke_frontend_flow.ps1`, `docs/20_runtime/testing/active_actor_integration_smoke.md`
- Tests: frontend smoke reruns with scenario variants.

### P2-10 Resource version switch rehearsal playbook
- Status: `TODO`
- Why: lower risk for prompt/flow/schema/policy version operations.
- Scope: `resources/README.md`, `resources/CHANGELOG.md`, `docs/30_resources/external_resources_and_trace.md`
- Tests: manual manifest toggle rehearsal plus targeted pytest rerun.

### P2-11 Runtime Context Architecture
- Status: `TODO`
- Why: long-running sessions still need a bounded context-builder path without changing current runtime authority.
- Scope: `docs/90_playable/P2_RUNTIME_CONTEXT_DEVELOPER_REFERENCE.md`, `docs/90_playable/P2_RUNTIME_CONTEXT_ARCHITECTURE_OVERVIEW.md`, `docs/90_playable/P2_CONTEXT_BUILDER_IMPLEMENTATION_PREP.md`, future `backend/app/turn_service.py` seam before `_build_system_prompt()`.
- Active sub-items:
  - `P2-11A Context Builder Infrastructure`
  - `P2-11B Recent History Window`
  - `P2-11C Focus Layer`
  - `P2-11D Structured Memory Framework`
  - `P2-11E State Memory`
  - `P2-11F Event Memory`
  - `P2-11G Memory Update Pipeline`
  - `P2-11H Fallback Recall System`
  - `P2-11I Context Token Budget Policy`
  - `P2-11J Context Builder Observability and Regression`
- Acceptance: context-builder work remains advisory only and does not introduce a second runtime authority.

### P2-12 Conflict detector false-positive reduction
- Status: `TODO`
- Why: unnecessary retries still degrade user experience.
- Scope: `backend/app/conflict_detector.py`, `backend/app/turn_service.py`
- Tests: `backend/tests/test_chat_semantic_guard.py`, `scripts/smoke_full_gameplay.ps1`.

### P2-14 Formal / preset alignment scope closure
- Status: `TODO`
- Why: the audit/backlog chain is implemented, but current preset formal coverage is intentionally narrow and should be explicitly frozen or deliberately expanded.
- Scope: `backend/app/formal_preset_mapper.py`, `backend/app/formal_preset_alignment_audit.py`, `backend/app/formal_preset_alignment_backlog.py`, `docs/01_specs/formal_gameplay_model_v0.md`, `backend/tests/test_formal_preset_adapter.py`
- Acceptance: `midnight_archive_world` remains documented as a `partial` single-route sample unless broader coverage is intentionally added.
- Tests: `backend/tests/test_formal_preset_adapter.py`, `backend/tests/test_formal_gameplay_v1.py`.

### P2-15 Character access read-boundary closure or freeze
- Status: `TODO`
- Why: runtime-facing character reads still rely on a stubbed boundary and need either a real closed path or an explicit freeze.
- Scope: `backend/domain/character_access.py`, related CharacterFact read docs, and the minimum tests/docs needed to make the boundary explicit.
- Acceptance: the runtime-facing character read seam is either closed on a real store path or documented as an intentionally frozen non-authoritative stub.
- Tests: `backend/tests/test_character_facade.py`, `backend/tests/test_character_fact_api.py`.

### P2-16 Frontend legacy surface cleanup
- Status: `TODO`
- Why: half-primary or legacy frontend surfaces should not continue to look like active gameplay entry points.
- Scope: `frontend/index.html`, `frontend/app.js`, `frontend/map.html`, `frontend/map.js`, `docs/20_runtime/frontend_entrypoints.md`, matching spec references.
- Acceptance: current primary entry points stay explicit and legacy surfaces are clearly demoted or deliberately retained with accurate docs.
- Tests: `frontend/tests/store_loop.test.mjs`, targeted manual entrypoint check.
