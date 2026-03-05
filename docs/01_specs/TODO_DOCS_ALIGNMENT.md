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
