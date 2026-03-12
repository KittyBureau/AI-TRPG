# TODO: Docs Alignment (Pending or Design-Only)

This file tracks known documentation items that do not match current backend/frontend
behavior or require future implementation. Update this file instead of scattering
TODOs across docs.

## docs/99_human_only/ai-trpg-design
- dialog_routing.md: Routing/context_profile/persona-lock pipeline described but not implemented.
  Impact: Misleads routing/config expectations for dialog_type and context building.
  Recommendation: Move to human-only or add a prominent "design-only" banner.
  Evidence: doc `docs/99_human_only/ai-trpg-design/dialog_routing.md`; code lacks keywords
  (`context_profile`, `persona_lock`, `dialog_route`) in `backend/**`.
  Status: moved to `docs/99_human_only/ai-trpg-design/dialog_routing.md` (design-only).

## CharacterFact behavior alignment (2026-03-03)
- Status: synchronized to test-authoritative wording.
- Scope:
  - `docs/01_specs/character_fact_v1.md` section 8 now separates Guaranteed vs Unspecified
    behavior for GET fact and generate error precedence.
  - `docs/20_runtime/testing/api_test_guide.md` includes the same matrices with explicit
    test file line references.

## Tool-success narrative fallback alignment (2026-03-10)
- Status: deferred doc wording update.
- Scope:
  - backend now injects minimal `narrative_text = "The action was performed."`
    when a turn has at least one successful applied action and the model returned
    empty assistant text.
  - current response shape is unchanged; only the success-path empty-text behavior
    was hardened for Playable v1 closure.
- Recommendation:
  - fold this behavior into `docs/20_runtime/testing/api_test_guide.md` and any
    matching runtime contract wording during the next P1 docs closure pass.
- Evidence:
  - `backend/app/turn_service.py`
  - `backend/tests/test_turn_response_contract_api.py`

## Playable scenario generator v0 design alignment (2026-03-12)
- Status: v0 closed loop implemented and lightly stabilized for pause.
- Scope:
  - `docs/90_playable/P2_PLAYABLE_SCENARIO_GENERATOR_V0.md` now records the watchtower extraction, `key_gate_scenario` template definition, parameter model, solvability rules, and minimal integration plan.
  - repo now also contains an internal-only scenario chain plus a guarded runtime compatibility path for metadata-backed `key_gate_scenario` worlds
  - one built-in scenario-backed preset is now available for internal development and validation of the guarded preset/bootstrap flow
  - `/api/v1/worlds/generate` now persists only normalized scenario generator metadata for supported playable-scenario worlds; topology and runtime content are still rebuilt later during campaign bootstrap/runtime
  - `frontend/panels/world_panel.js` now exposes only the minimal scenario parameter surface; this must still not be described as advanced scenario editing or a broader content system
  - world list and campaign world selection now expose only lightweight scenario readability fields (`scenario-backed`, template label, area count, difficulty)
- Recommendation:
  - Keep the design doc aligned to the current code seams in `backend/app/world_presets.py`, `backend/app/turn_service.py`, and `backend/app/tool_executor.py`.
  - Treat the `tool_executor.py` scenario move/goal fallback as a v0 compatibility bridge only, not as a general future expansion point.
  - Keep describing API-generated scenario worlds as metadata-backed resources, not persisted materialized worlds.
  - Treat Scenario Generator v0 as stabilized around the single `key_gate_scenario` path; future work should branch deliberately instead of continuing silent scope growth.
- Evidence:
  - `backend/app/scenario_runtime_mapper.py`
  - `backend/app/world_presets.py`
  - `backend/app/world_service.py`
  - `backend/app/turn_service.py`
  - `backend/app/tool_executor.py`
  - `frontend/panels/world_panel.js`
