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
- Status: design documented; runtime implementation pending.
- Scope:
  - `docs/90_playable/P2_PLAYABLE_SCENARIO_GENERATOR_V0.md` now records the watchtower extraction, `key_gate_scenario` template definition, parameter model, solvability rules, and minimal integration plan.
  - This document is intentionally design-only for now and must not be read as implemented runtime behavior.
- Recommendation:
  - Keep the design doc aligned to the current code seams in `backend/app/world_presets.py`, `backend/app/turn_service.py`, and `backend/app/tool_executor.py`.
  - Do not claim generated scenario support in user-facing runtime docs until campaign bootstrap and move/goal rule lookup are actually wired.
- Evidence:
  - `backend/app/world_presets.py`
  - `backend/app/turn_service.py`
  - `backend/app/tool_executor.py`
