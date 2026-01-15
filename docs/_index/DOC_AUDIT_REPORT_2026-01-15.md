# Docs Baseline Audit Report (2026-01-15)

## Summary
- Files checked: `docs/01_specs/**` = 7, `docs/02_guides/testing/**` = 2, `docs/03_reference/**` = 47, plus `docs/00_overview/README.md`.
- Hard claims extracted: 24 total.
- Mismatch: 16.
- Unproven: 3.
- OK: 5.

### Top 10 High-Risk Items
1) Legacy AI-TRPG reference specs (removed) listed `/session/new`, `/turn`, `/state`, `/logs`, `/tools/*` endpoints not implemented.
2) Legacy AI-TRPG turn request schema snapshots (removed) define `session_id/turn_id/user_text/intent`, but API expects `campaign_id/user_input/actor_id`.
3) Legacy AI-TRPG turn response schema snapshots (removed) define `say/options/tool_call` response, but API returns `narrative_text/tool_calls/applied_actions/...`.
4) Legacy AI-TRPG tool_call schema snapshot (removed) defines `name/arguments`, but code requires `id/tool/args/reason`.
5) Legacy AI-TRPG campaign snapshot (removed) does not match the persisted `Campaign` model (missing `selected`, `settings_snapshot`, `map`, etc.).
6) `docs/03_reference/codex-start/CODEX_PROMPT_AI_TRPG_stepwise.md` requires `/api/tools/execute`, but no `/api/tools/*` endpoints exist.
7) `docs/01_specs/architecture.md` says dialog_type is assigned by `DialogTypeClassifier` rules; runtime uses LLM output + fallback.
8) `docs/01_specs/conflict_and_retry.md` conflict report example includes `has_conflict`, but code only returns `retries` + `conflicts`.
9) `docs/02_guides/testing/api_test_guide.md` storage path claims `storage/{campaign_id}/campaign.json`, but code uses `storage/campaigns/<campaign_id>/campaign.json`.
10) `docs/03_reference/design/dialog_routing.md` describes routing/context-profile pipeline and persona-lock guards with no implementation evidence.

## Findings (ordered by severity)

### 1) API endpoints in legacy spec do not exist
- Document: Legacy AI-TRPG reference specs (removed) (API 4.1–4.6, Tools section)
- Hard claim: “POST `/session/new` / `/turn` / GET `/state` / `/logs` and `/tools/*` APIs exist.”
- Conclusion: Mismatch
- Code evidence: `backend/api/routes/campaign.py` (`@router.post("/create")`), `backend/api/routes/chat.py` (`@router.post("/turn")`), `backend/api/routes/settings.py` (`@router.get("/schema")`, `@router.post("/apply")`); no `/session` or `/tools` routes (`rg -n "/session|/tools" backend`).
- Minimal doc revision: Replace API list with current endpoints:
  - “POST `/api/campaign/create`”, “GET `/api/campaign/list`”, “POST `/api/campaign/select_actor`”, “POST `/api/chat/turn`”, “GET `/api/settings/schema`”, “POST `/api/settings/apply`”.
- Impact: Misleads API clients, tests, and tooling; will cause 404s and incorrect integration.

### 2) Turn request schema does not match runtime API
- Document: Legacy AI-TRPG turn request schema snapshots (removed)
- Hard claim: Request uses `{campaign_id, session_id, turn_id, user_text, intent}`.
- Conclusion: Mismatch
- Code evidence: `backend/api/routes/chat.py` (`class TurnRequest` with `campaign_id`, `user_input`, `actor_id`).
- Minimal doc revision: Replace with:
  - `{ "campaign_id": "camp_0001", "user_input": "...", "actor_id": "pc_001" }` (actor_id optional).
- Impact: Wrong client payloads, test failures, and inaccurate validation tooling.

### 3) Turn response schema does not match runtime API
- Document: Legacy AI-TRPG turn response schema snapshots (removed)
- Hard claim: Response uses `{say, options, tool_call, tool_result, server_time}`.
- Conclusion: Mismatch
- Code evidence: `backend/api/routes/chat.py` (`class TurnResponse` includes `narrative_text`, `dialog_type`, `tool_calls`, `applied_actions`, `tool_feedback`, `conflict_report`, `state_summary`).
- Minimal doc revision: Replace response example/schema with actual fields from `TurnResponse`.
- Impact: Breaks client rendering expectations and schema validation.

### 4) ToolCall schema key names are wrong
- Document: Legacy AI-TRPG tool_call schema snapshot (removed)
- Hard claim: ToolCall uses `{name, arguments}` only.
- Conclusion: Mismatch
- Code evidence: `backend/domain/models.py` (`class ToolCall` uses `id`, `tool`, `args`, optional `reason`).
- Minimal doc revision: Replace ToolCall schema with fields `id`, `tool`, `args`, optional `reason`.
- Impact: Tool call validation and parsing will reject real payloads.

### 5) Campaign JSON example is incompatible with persisted model
- Document: Legacy AI-TRPG campaign snapshot (removed)
- Hard claim: Campaign contains only `{campaign_id, name, created_at}`.
- Conclusion: Mismatch
- Code evidence: `backend/domain/models.py` (`class Campaign` requires `id`, `selected`, `settings_snapshot`, `map`, `state`, `goal`, `milestone`, etc.).
- Minimal doc revision: Either expand example to match `Campaign` model or add a “legacy snapshot” disclaimer in the file header.
- Impact: Misleads storage readers and migration scripts; incompatible tooling.

### 6) Tool endpoints in legacy JSON specs are not implemented
- Document: Legacy AI-TRPG tool endpoint schema snapshots (removed)
- Hard claim: `/tools/player_hp_reduce`, `/tools/summary_writeback`, `/tools/state_patch` exist.
- Conclusion: Mismatch
- Code evidence: No `backend/api/routes/tools.py` and no `/api/tools/*` route registration (`backend/api/main.py`).
- Minimal doc revision: Mark these as legacy or planned; point to current tool execution via `/api/chat/turn`.
- Impact: Causes incorrect client/tool integration plans and failing tests.

### 7) Dialog type source is misattributed in architecture flow
- Document: `docs/01_specs/architecture.md` (Stage 1 Data Flow step 4)
- Hard claim: “DialogTypeClassifier assigns dialog_type by rules.”
- Conclusion: Mismatch
- Code evidence: `backend/app/turn_service.py` (`_resolve_dialog_type` uses LLM output + fallback), no `DialogTypeClassifier` usage (`rg -n "DialogTypeClassifier" backend`).
- Minimal doc revision: Replace step 4 with “Dialog type is taken from LLM output; invalid/missing values fall back to `DEFAULT_DIALOG_TYPE`.”
- Impact: Misleads debugging and test assumptions about dialog type behavior.

### 8) Conflict report schema includes a non-existent field
- Document: `docs/01_specs/conflict_and_retry.md` (Example conflict report)
- Hard claim: Conflict report includes `has_conflict`.
- Conclusion: Mismatch
- Code evidence: `backend/domain/models.py` (`class ConflictReport` only has `retries` and `conflicts`); `backend/app/turn_service.py` builds that structure.
- Minimal doc revision: Remove `has_conflict` from the example and describe `{retries, conflicts}` only.
- Impact: Client parsing and tests may fail on missing field.

### 9) Storage path in test guide is incorrect
- Document: `docs/02_guides/testing/api_test_guide.md` (Step 1 and file checklist)
- Hard claim: “storage/ 下生成 campaign.json”; path list shows `storage/{campaign_id}/campaign.json`.
- Conclusion: Mismatch
- Code evidence: `backend/infra/file_repo.py` (`_campaign_path` uses `storage/campaigns/<campaign_id>/campaign.json`).
- Minimal doc revision: Replace with `storage/campaigns/<campaign_id>/campaign.json` and `storage/campaigns/<campaign_id>/turn_log.jsonl`.
- Impact: Manual testers will look in the wrong location; false negatives.

### 10) LLM config example filename in test guide is wrong
- Document: `docs/02_guides/testing/api_test_guide.md` (LLM 配置 Step 1)
- Hard claim: `storage/config/llm_config.example.json` exists.
- Conclusion: Mismatch
- Code evidence: Repo contains `storage/config/llm_config.example copy.json` and `storage/config/llm_config.json` (`rg --files storage -g "llm_config*"`).
- Minimal doc revision: Replace filename with `storage/config/llm_config.example copy.json` (or rename the file to match docs).
- Impact: Setup instructions fail; blocks Stage 4 testing.

### 11) HP state transition mentions “dead” but code never sets it
- Document: `docs/02_guides/testing/api_test_guide.md` (Step 6 validation)
- Hard claim: “character_states 正确进入 dying/dead.”
- Conclusion: Mismatch
- Code evidence: `backend/app/tool_executor.py` (`_apply_hp_delta` sets `dying` and restores `alive`; no `dead` assignment).
- Minimal doc revision: Replace with “character_states 进入 `dying`（当前实现无 `dead` 自动切换）”.
- Impact: Test expectations will never be satisfied; false failures.

### 12) tool_result_mismatch claim is inaccurate for no-tool-call narratives
- Document: `docs/02_guides/testing/map_generate_manual_test.md` (conflict_report section)
- Hard claim: “叙事声称执行工具但未发起 tool_call 时，conflict_report 可能记录 tool_result_mismatch.”
- Conclusion: Mismatch
- Code evidence: `backend/app/conflict_detector.py` only emits `tool_result_mismatch` when `tool_feedback` exists; no-tool-call case yields `state_mismatch` if narrative implies change.
- Minimal doc revision: Replace with “可能记录 `state_mismatch`（无 tool_call 时）”.
- Impact: Misinterprets conflict diagnostics during testing.

### 13) “No .html files found” is false
- Document: `docs/03_reference/reviews/capability_inventory.md` (Section H)
- Hard claim: “No `.html` files found; no static serving configuration.”
- Conclusion: Mismatch
- Code evidence: `frontend/index.html` exists (`rg --files -g "*.html" frontend`).
- Minimal doc revision: Change to “No static serving configured in backend; frontend HTML exists under `frontend/`.”
- Impact: Misleads frontend discovery and packaging steps.

### 14) “One tool_call per turn” claim conflicts with runtime
- Document: Legacy AI-TRPG README (removed) (关键约束)
- Hard claim: “一次对话最多一次 tool_call”.
- Conclusion: Mismatch
- Code evidence: `backend/app/turn_service.py` parses `tool_calls` as a list; no enforcement of single call.
- Minimal doc revision: Add “当前实现允许多个 tool_calls；单次限制为设计目标” or mark as legacy constraint.
- Impact: Misinforms tool integration and LLM prompt expectations.

### 15) “/api/tools/execute” endpoint referenced but absent
- Document: `docs/03_reference/codex-start/CODEX_PROMPT_AI_TRPG_stepwise.md` (Stage 3)
- Hard claim: “POST `/api/tools/execute` exists.”
- Conclusion: Mismatch
- Code evidence: No `/api/tools` routers; only `backend/api/routes/campaign.py`, `backend/api/routes/chat.py`, `backend/api/routes/settings.py`.
- Minimal doc revision: Mark as removed; describe tool execution only via `/api/chat/turn`.
- Impact: Directs developers to implement or call a non-existent endpoint.

### 16) LLM output schema in codex-start doc is wrong
- Document: `docs/03_reference/codex-start/CODEX_PROMPT_AI_TRPG_stepwise.md` (Stage 4 output protocol)
- Hard claim: “AI output must include `text` and `structured.tool_calls`.”
- Conclusion: Mismatch
- Code evidence: `backend/infra/llm_client.py` expects `assistant_text`, `dialog_type`, `tool_calls` at top level; `backend/app/turn_service.py` stores `assistant_structured.tool_calls`.
- Minimal doc revision: Replace with `assistant_text`, `dialog_type`, `tool_calls` (top-level) and note `assistant_structured` is generated server-side.
- Impact: Misaligns LLM prompt contract and parsing.

### 17) Dialog routing pipeline claims have no implementation evidence
- Document: `docs/03_reference/design/dialog_routing.md`
- Hard claim: “full_context pipeline, system prompt file loading, persona lock, route-driven context_profile exist.”
- Conclusion: Unproven
- Code evidence: No references to `context_profile`, `persona_lock`, `rules_text_path`, or route tables in backend/frontend (`rg -n "context_profile|persona_lock|dialog_route" backend frontend`).
- Minimal doc revision: Add a header disclaimer: “Design-only, not implemented; for future roadmap.”
- Impact: Engineers may assume routing infrastructure exists; leads to incorrect usage.

### 18) LLM test expectations are not enforced (nondeterministic)
- Document: `docs/02_guides/testing/api_test_guide.md` (Step 4)
- Hard claim: “无 tool_calls / applied_actions.”
- Conclusion: Unproven
- Code evidence: `backend/app/turn_service.py` uses LLM output `tool_calls`; no guard forcing empty tool_calls.
- Minimal doc revision: Replace with “通常为空（不保证）；只需记录系统返回值即可.”
- Impact: False failures in manual testing.

### 19) Retry expectation is nondeterministic
- Document: `docs/02_guides/testing/api_test_guide.md` (Step 7)
- Hard claim: “第一次生成被拦截，retry 发生.”
- Conclusion: Unproven
- Code evidence: `backend/app/conflict_detector.py` only triggers conflicts when narrative text matches heuristics; LLM output is not forced.
- Minimal doc revision: Replace with “可能触发 retry；为提高命中率，诱导叙事明确宣告状态变化.”
- Impact: Manual testers may misinterpret success/failure.

### 20) Storage layout validation rules match code
- Document: `docs/01_specs/storage_layout.md` (Map normalization and validation)
- Hard claim: “reachable ids are strings, no duplicates, no self-loop, targets exist, parent group connected.”
- Conclusion: OK
- Code evidence: `backend/domain/map_models.py` (`validate_map` and `require_valid_map`).
- Minimal doc revision: None.
- Impact: Validation expectations align with code.

### 21) Dialog types list and fallback match code
- Document: `docs/01_specs/dialog_types.md` (Types/Source Field)
- Hard claim: `scene_description/action_prompt/resolution_summary/rule_explanation`, fallback to `scene_description`, source `model|fallback`.
- Conclusion: OK
- Code evidence: `backend/domain/dialog_rules.py` (`DIALOG_TYPES`, `DEFAULT_DIALOG_TYPE`), `backend/app/turn_service.py` (`_resolve_dialog_type`).
- Minimal doc revision: None.
- Impact: Safe to rely on enum/fallback behavior.

### 22) Settings registry keys and validation match code
- Document: `docs/01_specs/settings.md` (Registry keys, validation, range)
- Hard claim: Five keys, mutual exclusion, range `0..10`.
- Conclusion: OK
- Code evidence: `backend/domain/settings.py` (`_DEFINITIONS`, `_validate_snapshot`).
- Minimal doc revision: None.
- Impact: Settings tests align with runtime validation.

### 23) Tool parameters and failure reasons match code
- Document: `docs/01_specs/tools.md` (Allowed tools, required args, failure reasons)
- Hard claim: `move`, `hp_delta`, `map_generate` with error reasons `tool_not_allowed`, `invalid_args`, `actor_state_restricted`, `invalid_actor_state`.
- Conclusion: OK
- Code evidence: `backend/app/tool_executor.py` and `backend/domain/state_machine.py`.
- Minimal doc revision: None.
- Impact: Tool validation guidance matches runtime.

### 24) MAP_TEST_* env flags match test script
- Document: `docs/02_guides/testing/map_generate_manual_test.md` (MAP_TEST_STRICT/MAP_TEST_MAX_ATTEMPTS)
- Hard claim: Env vars `MAP_TEST_STRICT` and `MAP_TEST_MAX_ATTEMPTS` control test behavior.
- Conclusion: OK
- Code evidence: `backend/tests/test_map.py` (`MAX_ATTEMPTS`, `STRICT_MODE`).
- Minimal doc revision: None.
- Impact: Manual test instructions are accurate.

## Outdated handling
`docs/03_reference/reviews/CODE_REVIEW_2026-01-09.md` is outdated relative to the 2026-01-14 refactor.  
Recommendation: **Move to `_archive`** (reason: it enumerates endpoints and architecture no longer present and will mislead future audits).  
Alternative if you prefer to keep it visible: add a bold “Outdated (pre-2026-01-14 refactor)” banner at the top.

## Optional improvements
- Add a short “legacy / design-only, not implemented” banner to `docs/03_reference/codex-start/**` where they define APIs and schemas that no longer match runtime.
