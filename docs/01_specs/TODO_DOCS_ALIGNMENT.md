# TODO: Docs Alignment (Pending or Design-Only)

This file tracks known documentation items that do not match current backend/frontend
behavior or require future implementation. Update this file instead of scattering
TODOs across docs.

## docs/03_reference/design
- dialog_routing.md: Routing/context_profile/persona-lock pipeline described but not implemented.
  Impact: Misleads routing/config expectations for dialog_type and context building.
  Recommendation: Move to human-only or add a prominent "design-only" banner.
  Evidence: doc `docs/03_reference/design/dialog_routing.md`; code lacks keywords
  (`context_profile`, `persona_lock`, `dialog_route`) in `backend/**`.

## docs/03_reference/codex-start
- CODEX_PROMPT_AI_TRPG_stepwise.md: References `/api/tools/execute` and a tool execution pipeline
  not present in the current API.
  Impact: Sends developers toward non-existent endpoints.
  Recommendation: Update to current endpoints or mark as legacy input.
  Evidence: doc `docs/03_reference/codex-start/CODEX_PROMPT_AI_TRPG_stepwise.md`; API routes
  in `backend/api/routes/*.py`.

- CODEX_PROMPT_AI_TRPG_stepwise.md: LLM output schema uses `text` + `structured.tool_calls`,
  but implementation parses top-level `assistant_text`, `dialog_type`, `tool_calls`.
  Impact: Misaligns prompt contract and parsing.
  Recommendation: Update schema or add a legacy disclaimer.
  Evidence: doc `docs/03_reference/codex-start/CODEX_PROMPT_AI_TRPG_stepwise.md`; parser
  in `backend/infra/llm_client.py` and response building in `backend/app/turn_service.py`.

## docs/03_reference/reviews
- capability_inventory.md: Claims no `.html` files found, but `frontend/index.html` exists.
  Impact: Misleads frontend discovery/packaging.
  Recommendation: Update statement or mark as outdated.
  Evidence: doc `docs/03_reference/reviews/capability_inventory.md`; file `frontend/index.html`.
