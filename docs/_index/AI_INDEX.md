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
- `/api/chat/turn` responses include `narrative_text`, `dialog_type`, `tool_calls`, `applied_actions`, `tool_feedback`, `conflict_report`, and `state_summary`.
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
- Exercise `/api/chat/turn` to confirm fallback behavior.
**Scope**
- `backend/domain/dialog_rules.py`, `backend/app/turn_service.py`, `docs/01_specs/dialog_types.md`.

## 4. Settings Registry & Validation
**Rules**
- Settings keys must exist in `backend/domain/settings.py`; unknown keys are rejected.
- `apply_settings_patch` enforces type/range rules and mutual exclusion; changed patches increment `settings_revision`.
- Settings are stored in `campaign.json.settings_snapshot`.
**Checks**
- Use `/api/settings/schema` and `/api/settings/apply` to verify definitions and patches.
- Update `docs/01_specs/settings.md` for any key changes.
**Scope**
- `backend/domain/settings.py`, `backend/app/settings_service.py`, `backend/api/routes/settings.py`, `docs/01_specs/settings.md`, `docs/01_specs/storage_layout.md`.

## 5. Tool Calls Protocol & Execution
**Rules**
- Each tool call includes `id`, `tool`, `args`; `tool` must be in `campaign.allowlist`.
- Invalid args return `tool_feedback.failed_calls` with `status`=`error` or `rejected` and a documented `reason`.
- Tool params and allowlist follow `docs/01_specs/tools.md`.
**Checks**
- Run `backend/tests/test_map_generate.py` when touching tool execution or validation.
- Review `docs/01_specs/tools.md` for param and reason updates.
**Scope**
- `backend/app/tool_executor.py`, `backend/domain/models.py`, `docs/01_specs/tools.md`, `backend/tests/test_map_generate.py`.

## 6. Storage Layout & Persistence
**Rules**
- Campaigns persist at `storage/campaigns/<campaign_id>/campaign.json`; turns append to `turn_log.jsonl` via `FileRepo`.
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
- Conflict types include `state_mismatch`, `tool_result_mismatch`, `forbidden_change` (rule_explanation only checks forbidden change).
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
**Checks**
- Review `backend/domain/state_machine.py` and tool executor behavior.
- Add or update tests when changing state permission logic.
**Scope**
- `backend/domain/state_machine.py`, `backend/app/tool_executor.py`, `docs/01_specs/state_machine.md`.

## 10. Tests & Gatekeeping
**Rules**
- API contract changes require updating `docs/02_guides/testing/api_test_guide.md`.
- Tool/state/map changes require running `backend/tests/test_map_generate.py` and reviewing the manual map_generate guide.
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
- Reference/legacy docs are non-authoritative; do not treat them as implementation truth.
- When modifying backend/frontend API routes, request/response fields, status codes, storage paths, JSON keys, enums, or settings keys/defaults/validation, you must update the matching docs.
- Every code commit touching those areas must include at least one docs update, or add a tracked entry to `docs/01_specs/TODO_DOCS_ALIGNMENT.md` explaining why the docs change is deferred.
**Checks**
- Confirm updated docs cover API routes, storage layout, enums, and settings changes.
- If docs are deferred, ensure `docs/01_specs/TODO_DOCS_ALIGNMENT.md` contains a dated entry with evidence.
**Scope**
- `backend/**`, `frontend/**`, `docs/00_overview/**`, `docs/01_specs/**`, `docs/02_guides/**`, `docs/01_specs/TODO_DOCS_ALIGNMENT.md`.
