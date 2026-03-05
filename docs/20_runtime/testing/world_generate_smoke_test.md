# world_generate v1 Local Smoke Test

## Purpose

Provide a reusable local smoke test for `world_generate` without relying on a real LLM provider.

## Prerequisites

- Run from repository root.
- Python environment with project dependencies installed.
- Windows PowerShell for the provided script.

## Script

- `scripts/smoke_world_generate.ps1`
- helper server: `scripts/smoke_world_generate_server.py`

The helper server patches `TurnService` LLM client in-process for deterministic tool outputs and does not modify business implementation files.

## Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1
```

To keep artifacts for inspection:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1 -KeepWorkspace
```

## Covered cases

1. No `world_id` and campaign unbound:
   - expect `tool_feedback.failed_calls[0].reason == "world_id_missing"`
2. Explicit `world_id`:
   - expect `result.created == true`
   - expect `storage/worlds/<world_id>/world.json` exists
3. Repeat same `world_id`:
   - expect `seed` unchanged
   - expect `generator_id` unchanged
   - expect `updated_at` unchanged
4. `bind_to_campaign=true`:
   - expect `campaign.selected.world_id` persisted
   - subsequent no-arg `world_generate` succeeds using bound world

## Validation points (file-level)

- Campaign file:
  - `storage/campaigns/<campaign_id>/campaign.json`
  - field: `selected.world_id`
- World file:
  - `storage/worlds/<world_id>/world.json`
  - fields: `seed`, `generator.id`, `updated_at`

## Notes

- Temporary smoke workspace defaults to:
  - `.tmp/smoke_world_generate/`
- `.tmp/` is ignored by git and should not be committed.
