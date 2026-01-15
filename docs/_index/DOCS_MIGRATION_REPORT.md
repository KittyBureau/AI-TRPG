# Docs Migration Report

Date: 2026-01-15

## New Layout

- `docs/00_overview/` for entry points and the docs index.
- `docs/01_specs/` for authoritative, frozen specifications.
- `docs/02_guides/` for current how-to and testing workflows.
- `docs/03_reference/` for legacy/reference inputs and reviews.
- `docs/_archive/` for historical or task-only docs.
- `docs/_index/` for AI_INDEX, manifest, and task prefix.

## Docs Inventory (Post-Migration)

| Path | Topic | Status | Related Modules | Notes |
| --- | --- | --- | --- | --- |
| docs/00_overview/README.md | Docs index | overview | docs | Entry points and navigation. |
| docs/01_specs/architecture.md | Layering + turn flow | authoritative spec | backend/api, backend/app, backend/domain, backend/infra | Updated to reflect LLMClient. |
| docs/01_specs/storage_layout.md | Storage layout + schemas | authoritative spec | backend/infra/file_repo.py, backend/domain/models.py | Includes map validation rules. |
| docs/01_specs/settings.md | Settings registry + API | authoritative spec | backend/domain/settings.py | Key registry + validation. |
| docs/01_specs/dialog_types.md | Dialog types | authoritative spec | backend/domain/dialog_rules.py | Enum + fallback rules. |
| docs/01_specs/tools.md | Tool protocol | authoritative spec | backend/app/tool_executor.py | Params + failure reasons. |
| docs/01_specs/state_machine.md | State machine | authoritative spec | backend/domain/state_machine.py | Tool permission matrix. |
| docs/01_specs/conflict_and_retry.md | Conflict guard + retry | authoritative spec | backend/app/conflict_detector.py | LLM config + retry flow. |
| docs/02_guides/testing/api_test_guide.md | API test guide | guide | backend/api | Current API smoke/regression steps. |
| docs/02_guides/testing/map_generate_manual_test.md | Manual map_generate test | guide | backend/tests/test_map.py | Focused regression/smoke guide. |
| docs/99_human_only/ai-trpg-design/ | Legacy AI-TRPG design notes | human-only | legacy backend/services | Preserved for human context only. |
| docs/99_human_only/ai-trpg-design/dialog_routing.md | Dialog routing design | human-only | legacy routing stack | Not wired in current code. |
| docs/03_reference/workflows/cursor_chatgpt_codex_workflow.md | Workflow notes | reference | docs | Process reference. |
| docs/03_reference/reviews/CODE_REVIEW_2026-01-09.md | Legacy review | reference | legacy backend/services | Snapshot of earlier architecture. |
| docs/_archive/2026-01-15/legacy/ | Legacy guides/tests | archived | legacy backend/services | Not aligned to current implementation. |
| docs/_archive/2026-01-15/ai/ | Legacy AI index/rules | archived | docs | Superseded by AI_INDEX. |
| docs/_archive/2026-01-15/temp/ | Temp prompts/drafts | archived | docs | Historical prompts/drafts. |
| docs/_index/AI_INDEX.md | Code constraints index | authoritative index | backend, docs | Sectioned rules + checks. |
| docs/_index/ai_index_manifest.json | AI_INDEX manifest | authoritative index | docs | Sections, paths, triggers. |
| docs/_index/CODEX_TASK_PREFIX.md | Codex prefix | authoritative index | docs | Copy/paste task prefix. |
| docs/_index/DOCS_MIGRATION_REPORT.md | Migration report | authoritative index | docs | This report. |

## New Docs Added

- `docs/00_overview/README.md`
- `docs/01_specs/*` (authoritative specs aligned to current backend)
- `docs/02_guides/testing/api_test_guide.md`
- `docs/02_guides/testing/map_generate_manual_test.md`
- `docs/_index/AI_INDEX.md`
- `docs/_index/ai_index_manifest.json`
- `docs/_index/CODEX_TASK_PREFIX.md`
- `docs/_index/DOCS_MIGRATION_REPORT.md`
- `docs/_archive/2026-01-15/codex_docs_cleanup_and_ai_index_prompt.md`

## Migration Mapping (Old -> New)

| Old Path | New Path / Status | Reason |
| --- | --- | --- |
| docs/01_architecture.md | docs/01_specs/architecture.md | Spec moved under authoritative specs. |
| docs/02_storage_layout.md | docs/01_specs/storage_layout.md | Spec moved under authoritative specs. |
| docs/03_settings.md | docs/01_specs/settings.md | Spec moved under authoritative specs. |
| docs/04_dialog_types.md | docs/01_specs/dialog_types.md | Spec moved under authoritative specs. |
| docs/05_tools.md | docs/01_specs/tools.md | Spec moved under authoritative specs. |
| docs/06_state_machine.md | docs/01_specs/state_machine.md | Spec moved under authoritative specs. |
| docs/07_conflict_and_retry.md | docs/01_specs/conflict_and_retry.md | Spec moved under authoritative specs. |
| docs/test/API_TEST_GUIDE.md | docs/02_guides/testing/api_test_guide.md | Guide moved into testing guides. |
| docs/test/人工测试说明文档.md | docs/02_guides/testing/map_generate_manual_test.md | Guide renamed to ASCII filename and moved. |
| docs/reviews/CODE_REVIEW_2026-01-09.md | docs/03_reference/reviews/CODE_REVIEW_2026-01-09.md | Review moved to reference section. |
| docs/cursor_chatgpt_codex_workflow.md | docs/03_reference/workflows/cursor_chatgpt_codex_workflow.md | Workflow note moved to reference section. |
| docs/design/dialog_routing.md | docs/99_human_only/ai-trpg-design/dialog_routing.md | Legacy design doc moved to human-only. |
| docs/ai-trpg/design/framework.md | docs/99_human_only/ai-trpg-design/framework.md | Legacy design doc moved to human-only. |
| docs/ai-trpg/design/mainline_milestones.md | docs/99_human_only/ai-trpg-design/mainline_milestones.md | Legacy design doc moved to human-only. |
| docs/ai-trpg/design/mainline_protection_mechanism.md | docs/99_human_only/ai-trpg-design/mainline_protection_mechanism.md | Legacy design doc moved to human-only. |
| docs/ai-trpg/design/probabilistic_resolution_layer.md | docs/99_human_only/ai-trpg-design/probabilistic_resolution_layer.md | Legacy design doc moved to human-only. |
| docs/ai-trpg/design/reality_guards.md | docs/99_human_only/ai-trpg-design/reality_guards.md | Legacy design doc moved to human-only. |
| docs/ai-trpg/specs/** | removed | Legacy specs removed from repo. |
| docs/ai-trpg/project/** | removed | Legacy project notes removed from repo. |
| docs/ai-trpg/prompts/** | removed | Legacy prompts removed from repo. |
| docs/ai-trpg/runs/2026-01-06_trpg_test/internal_notes.md | docs/_archive/2026-01-15/ai-trpg/runs/2026-01-06_trpg_test/internal_notes.md | Run logs archived. |
| docs/ai-trpg/runs/2026-01-06_trpg_test/milestone_log.md | docs/_archive/2026-01-15/ai-trpg/runs/2026-01-06_trpg_test/milestone_log.md | Run logs archived. |
| docs/ai/AI_INDEX.md | docs/_archive/2026-01-15/ai/AI_INDEX.md | Legacy AI docs archived. |
| docs/ai/ARCHITECTURE.md | docs/_archive/2026-01-15/ai/ARCHITECTURE.md | Legacy AI docs archived. |
| docs/ai/CHANGELOG_AI.md | docs/_archive/2026-01-15/ai/CHANGELOG_AI.md | Legacy AI docs archived. |
| docs/ai/CHECKLIST.md | docs/_archive/2026-01-15/ai/CHECKLIST.md | Legacy AI docs archived. |
| docs/ai/CODE_REVIEW_PROMPT.md | docs/_archive/2026-01-15/ai/CODE_REVIEW_PROMPT.md | Legacy AI docs archived. |
| docs/ai/CONVENTIONS.md | docs/_archive/2026-01-15/ai/CONVENTIONS.md | Legacy AI docs archived. |
| docs/ai/DECISIONS.md | docs/_archive/2026-01-15/ai/DECISIONS.md | Legacy AI docs archived. |
| docs/testing/dialog_routing_test_method.md | docs/_archive/2026-01-15/legacy/dialog_routing_test_method.md | Legacy guide archived. |
| docs/human/LEARNING_PATH.md | docs/_archive/2026-01-15/legacy/learning_path.md | Legacy guide archived. |
| docs/PLAY_GUIDE_MIN.md | docs/_archive/2026-01-15/legacy/play_guide_min.md | Legacy guide archived. |
| docs/temp/chat_with_context_00.md | docs/_archive/2026-01-15/temp/chat_with_context_00.md | Temp prompt archived. |
| docs/temp/codex_multi_key_openai_compat_prompt.md | docs/_archive/2026-01-15/temp/codex_multi_key_openai_compat_prompt.md | Temp prompt archived. |
| docs/temp/codex_path_refactor_prompt.md | docs/_archive/2026-01-15/temp/codex_path_refactor_prompt.md | Temp prompt archived. |
| docs/temp/codex_prompt_context_v0.md | docs/_archive/2026-01-15/temp/codex_prompt_context_v0.md | Temp prompt archived. |
| docs/temp/codex_route_prompt.md | docs/_archive/2026-01-15/temp/codex_route_prompt.md | Temp prompt archived. |
| docs/temp/codex_secrets_prompt.md | docs/_archive/2026-01-15/temp/codex_secrets_prompt.md | Temp prompt archived. |
| docs/temp/how_to_start.md | docs/_archive/2026-01-15/temp/how_to_start.md | Temp prompt archived. |
| docs/temp/web_chatgpt_progress_update.md | docs/_archive/2026-01-15/temp/web_chatgpt_progress_update.md | Temp prompt archived. |
| docs/TODO_CONTEXT.md | docs/_archive/2026-01-15/todo_context.md | Legacy TODO archived. |
| docs/temp/codex_docs_cleanup_and_ai_index_prompt.md | docs/_archive/2026-01-15/codex_docs_cleanup_and_ai_index_prompt.md | Task prompt archived. |

## Merges / Deprecations

- No merges were required; legacy docs were moved to reference or archive.

## Conflicts / Gaps Found

- Legacy docs reference a different architecture (`backend/services`, `/api/chat/send`), so they were moved to human-only or removed to avoid mixing with current specs.
- The AI/AI-TRPG legacy doc sets are kept for context (human-only) but are not authoritative for the current backend.
- API contract knowledge is split across code and guides; no single formal API schema exists for the current implementation.

## Maintenance Notes

- Keep `docs/01_specs/` authoritative: update specs before or alongside code changes.
- Update `docs/_index/AI_INDEX.md` when manifest trigger paths are touched.
- Treat `docs/03_reference/**` and `docs/_archive/**` as legacy unless explicitly revived.
- If new protocol fields or enums are added, add/extend a spec in `docs/01_specs/` and list it in `docs/_index/ai_index_manifest.json`.
