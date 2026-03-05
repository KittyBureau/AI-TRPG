# Documentation Index

## Entry Points

- `docs/00_overview/README.md` - Primary docs entry.
- `docs/00_overview/DOCS_PATH_MAPPING.md` - One-time migration mapping and rollback map.
- `docs/_index/AI_INDEX.md` - Task constraints and verification checkpoints.
- `docs/_index/CODEX_TASK_PREFIX.md` - Prompt prefix for Codex tasks.

## Core Specs (Authoritative)

- `docs/01_specs/architecture.md`
- `docs/01_specs/storage_layout.md`
- `docs/01_specs/settings.md`
- `docs/01_specs/dialog_types.md`
- `docs/01_specs/tools.md`
- `docs/01_specs/state_machine.md`
- `docs/01_specs/conflict_and_retry.md`
- `docs/01_specs/character_baseline.md`
- `docs/01_specs/character_access_boundary.md`
- `docs/01_specs/character_fact_v1.md`
- `docs/01_specs/schemas/character_fact.v1.schema.json`
- `docs/01_specs/prompts/character_fact_generate_v1.md`

## Runtime Guides

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

- `docs/90_playable/PLAYABLE_V1_TODO.md` - Playable v1 development mainline TODO.

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
