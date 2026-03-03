# V1.1 Alignment Summary - Implementation Update (2026-03-03)

## 1. Scope
This document summarizes the implementation alignment for the approved V1.1 roadmap baseline (P0 -> P1 -> P2), based on:
- `CODEX_TODO_Conflict_Audit_Prompt.md`
- `CODEX_Full_TODO_Roadmap_Prompt.md`
- User decisions locked in this session

## 2. Locked Decisions Applied
- Roadmap is the V1.1 execution baseline.
- Multi-actor unconscious behavior: reject current turn and require manual actor switch (no auto-skip).
- Sidecar/turn_log concurrency hardening is out of V1.1 scope; single-process semantics retained.
- Delivery order kept as P0 -> P1 -> P2.

## 3. Delivered Work

### P0 Lifecycle + Milestone + Turn Flow Guard
- Added optional lifecycle model to campaign data (`ended`, `reason`, `ended_at`) with backward-compatible defaults.
- Added milestone rhythm fields (`turn_trigger_interval`, `pressure`, `pressure_threshold`, `summary`) with defaults.
- Turn pre-check and post-check now support campaign end-state enforcement.
- Ended campaign behavior: no write via turn flow; read routes remain available.
- Active actor unconscious now returns explicit manual-switch guidance.
- `context.compress_enabled` is now wired into system prompt context mode (`full` vs `compressed`).

### P1 Guarding + Conflict/Repeat + CharacterFact Adoption
- Added strict dialog semantic guard switch (`dialog.strict_semantic_guard`, default `false`).
- Default behavior remains fallback-compatible; strict mode rejects invalid dialog_type with HTTP 422.
- Conflict detection text checks are now setting-gated (`dialog.conflict_text_checks_enabled`, default `false`).
- Added repeat-illegal-request suppression (last 3 turns, tool+args signature, turn_log backread).
- Implemented CharacterFact adoption flow:
  - No schema changes to draft payload.
  - Sidecar acceptance file added:
    - `storage/campaigns/{campaign_id}/characters/generated/{character_id}.fact.accepted.json`
  - Static profile write boundary enforced via `campaign.actors[*].meta.profile`.
  - Runtime fields are not overwritten.
  - Idempotent re-adoption behavior validated.

### P2 Observability Routes
- Added campaign status endpoint for lifecycle + milestone visibility.
- Added optional manual milestone advance endpoint for controlled operations.

## 4. Key Files Updated
- `backend/domain/models.py`
- `backend/domain/settings.py`
- `backend/app/turn_service.py`
- `backend/app/conflict_detector.py`
- `backend/app/character_fact_api_service.py`
- `backend/infra/file_repo.py`
- `backend/api/routes/chat.py`
- `backend/api/routes/characters.py`
- `backend/api/routes/campaign.py`

## 5. Tests Added/Updated
### New
- `backend/tests/test_turn_service_lifecycle.py`
- `backend/tests/test_chat_semantic_guard.py`
- `backend/tests/test_campaign_observability_api.py`

### Updated
- `backend/tests/test_character_fact_api.py`

## 6. Validation Summary
Executed and passed:
- `backend/tests/test_turn_service_lifecycle.py`
- `backend/tests/test_chat_semantic_guard.py`
- `backend/tests/test_campaign_observability_api.py`
- `backend/tests/test_character_fact_api.py`
- `backend/tests/test_move.py`
- `backend/tests/test_move_options.py`
- `backend/tests/test_api_v1_routing.py`

Result: all targeted tests passed.

## 7. Non-Breaking Alignment Check
- Existing route shapes retained.
- Existing response field structures retained for locked endpoints.
- Locked CharacterFact fallback/422/404/409 semantics preserved.
- Strict behaviors are behind default-off switches.

## 8. Remaining Notes
- Concurrency/locking remains intentionally out of scope for V1.1 (single-process assumption).
- Future hardening can be introduced via lock-provider extension points without changing current API contracts.
