# Documentation Index

## Entry Points

- `README.md` - Local quick start and first-run bootstrap.
- `docs/00_overview/README.md` - Primary docs entry.
- `docs/00_overview/DOCS_PATH_MAPPING.md` - One-time migration mapping and rollback map.
- `docs/_index/AI_INDEX.md` - Task constraints and verification checkpoints.
- `docs/_index/CODEX_TASK_PREFIX.md` - Prompt prefix for Codex tasks.

## Documentation Operations

- Primary development remains local: VSCode + Codex + the full repository are the authoritative working environment.
- ChatGPT web project context uses a lightweight Google Drive reference-doc package for structure, navigation, status, and roadmap context only.
- The synced package is not a second repo mirror; detailed implementation reading should still happen from the local repository, usually through Codex.
- Minimal sync checklist: `docs/01_specs/DOC_SYNC_BASELINE.md`.
- Refresh the lightweight package at milestone or phase wrap-up when project structure, high-level architecture, current status, or roadmap docs materially change.
- Standard refresh path: `scripts/sync_chatgpt_docs.ps1` (one-way overwrite upload from local to Drive).

## Core Specs (Authoritative)

- `docs/01_specs/architecture.md`
- `docs/01_specs/item_system_v2.md`
- `docs/01_specs/storage_layout.md`
- `docs/01_specs/settings.md`
- `docs/01_specs/dialog_types.md`
- `docs/01_specs/tools.md`
- `docs/01_specs/state_machine.md`
- `docs/01_specs/conflict_and_retry.md`
- `docs/01_specs/character_baseline.md`
- `docs/01_specs/character_access_boundary.md`
- `docs/01_specs/character_fact_v1.md`
- `docs/01_specs/generated_fact_foundation.md`
- `docs/01_specs/npc_memory_minimal.md`
- `docs/01_specs/formal_gameplay_model_v0.md`
- `docs/01_specs/schemas/character_fact.v1.schema.json`
- `docs/01_specs/prompts/character_fact_generate_v1.md`

## Current Formal Layer

- Formal Gameplay Model is currently a read-only, non-authoritative design-time and validation-time layer.
- Current implemented coverage includes:
  - `dependency_groups` with `all_of` / `any_of`
  - `multi_path_coverage`
  - `clue_support_coverage`
  - gate/overall quality aggregation
  - gate/overall authoring audit
  - generator-side shaping via `gate_clue` and `gate_clue_support_gap`
  - preset alignment audit via `alignment_level` and `priority_hint`
  - remediation backlog output via `gap_type`, `recommended_target`, and backlog summary
- Current preset alignment samples are:
  - `midnight_archive_world` as the current `partial` single-route sample
  - `test_watchtower_world` as the legacy baseline
- These outputs do not affect runtime authority, turn execution, or tool execution.

## Current Scenario Runtime Closure

- Scenario-generated campaigns now persist `Campaign.scenario_runtime_fragment` as the only runtime gate/goal authority.
- Scenario execution no longer depends on scenario compatibility shim/fallback paths after bootstrap.
- Current regression coverage locks this contract across multiple topology variants plus explicit missing/corrupt fragment failures.

## Current Gameplay Validation Layer

- Scenario generation now fails early when the current key-gate contract has no reachable completion path, no satisfiable gate dependency path, or an obvious dead-end layout.
- Generation also fails when the critical clue path is missing, placed after the dependency point, or structurally bound to the wrong source/item/area.
- Runtime now persists per-entity hostility and triggers `interaction_locked` at threshold instead of leaving high-conflict turns as narrative-only responses.
- If the locked interaction is the critical reveal source for the current scenario path, runtime performs a minimal progression re-check and triggers `progression_locked`, ending the campaign lifecycle.
- Runtime also has a minimal combat-entry branch: assaultive NPC `talk` can trigger one-shot `combat_resolved`, persist it under `Campaign.hostility`, and currently resolve to either default `player_repelled` or opt-in `npc_disabled`.
- `player_repelled` keeps the target on the existing talk lockout path; `npc_disabled` additionally leaves the NPC structurally disabled and blocks later `inspect`/`talk` interactions.
- The current recommended authoring shape for searchable aftermaths is `combat_aftermath_hook={"kind":"search_loot","item_id":"...","item_label":"..."}` on the target NPC.
- Selected `npc_disabled` aftermaths can use that hook so the result enters the existing `search`/reveal/take structure instead of remaining only a combat tag.
- Legacy `combat_reveal_item_id` / `combat_reveal_item_label` authoring still maps into that same searchable-aftermath contract for compatibility.
- `midnight_archive_world` now uses that contract on `janitor_npc` as the first real playable sample: disabling the janitor can expose a `routing_slip` source that still feeds into the normal service-route gate.
- This runtime/gameplay validation line is now closed through Phase 10. The next planned step is limited multi-node aftermath validation inside `midnight_archive_world`, not broader combat-system expansion or new hook kinds.
- This remains a bounded runtime hook, not a full combat system.

## Runtime Guides

- `frontend/README_frontend.md` - Static frontend local serving and backend base URL notes.
- `docs/20_runtime/item_runtime_model.md` - Stack-first item authority, reveal/take flow, gate check shape, and bounded legacy `inventory_add`.
- `docs/20_runtime/gameplay_flow.md` - End-to-end gameplay flow and UI/API chain.
- `docs/20_runtime/api_v1_route_migration.md` - `/api/v1` route migration note.
- `docs/20_runtime/frontend_entrypoints.md` - Frontend panel architecture and entry policy.
- `docs/20_runtime/storage_authority.md` - Actors authority and legacy mirror policy.
- `docs/20_runtime/testing/api_test_guide.md` - Authoritative API testing guide.
- `docs/02_guides/testing/playable_v1_manual_test.md` - Playable v1 manual verification suite.

## Resources / Architecture Notes

- `docs/30_resources/external_resources_and_trace.md` - External resource loading, hashes, fallback, trace.
- `docs/30_resources/debug_trace_contract.md` - `debug.resources` structure, trace gate, legacy compatibility.
- `resources/README.md` - Resource manifest ops and rollback procedure.
- `resources/CHANGELOG.md` - Resource change history.

## Playable Planning

- `docs/90_playable/PLAYABLE_V1_TODO.md` - Active playable backlog only.
- `docs/90_playable/ITEM_REFACTOR_CLOSURE_TODO.md` - Final closure status for the completed stack-first item refactor line.

## Compatibility Paths (Temporary)

- `docs/02_guides/**` and `docs/03_architecture/**` now contain migration notes for moved docs.
- `docs/test/API_TEST_GUIDE.md` is retained as a redirect note to the authoritative runtime guide.

## Frontend Entry

- Primary UI: `frontend/play.html`
- Debug UI: `frontend/debug.html`
- Deprecated redirect: `frontend/index.html`

## Reference / Human-Only

- Reference inputs: `docs/03_reference/codex-start/`
- Human-only notes: `docs/99_human_only/`
- Archive history: `docs/_archive/`
