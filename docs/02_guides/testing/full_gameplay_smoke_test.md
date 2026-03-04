# Full Gameplay Smoke Test

## Purpose

Provide a deterministic, regression-friendly gameplay loop test for the MVP path without changing business implementation.

Fixed chain:

1. `create_campaign`
2. `world_generate`
3. `map_generate`
4. `actor_spawn`
5. `move_options` (included in this smoke)
6. `move`
7. `chat/turn` narrative-only turn (at least one)

## Files

- `scripts/smoke_full_gameplay.ps1`
- `scripts/smoke_full_gameplay_server.py`
- `backend/tests/test_full_gameplay_loop.py`

## Run Commands

PowerShell smoke (one-click):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1
```

Keep workspace for inspection:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1 -KeepWorkspace
```

Run pytest integration test:

```powershell
python -m pytest backend/tests/test_full_gameplay_loop.py -q
```

## Workspace Isolation

Default workspace is per-run:

- `.tmp/smoke_full_gameplay/<run_id>`

Artifacts under workspace:

- `storage/campaigns/<campaign_id>/campaign.json`
- `storage/campaigns/<campaign_id>/turn_log.jsonl`
- `storage/worlds/<world_id>/world.json`

## PASS/FAIL Output Contract

Smoke script prints:

- run command hints
- per-step `PASS` lines
- final summary: `Result: PASS (...)` or `Result: FAIL (...)`

On failure, it prints shortest location in this format:

- `定位: <步骤> -> <字段> -> <文件路径>:<行号> | <错误说明>`

Example:

- `定位: move -> actors.pc_001.position -> .../campaign.json:123 | pc_001 position mismatch`

## Key Assertions

- `world_generate`: world persisted and bound to campaign
  - `campaign.json`: `selected.world_id`
  - `world.json`: `world_id`, `seed`, `generator.id`
- `map_generate`: created area ids persisted in `campaign.map.areas`
- `actor_spawn`: actor persisted and bound to party
  - `campaign.json`: `actors.<spawned_actor_id>`, `selected.party_character_ids`
- `move`: `actors.pc_001.position == "area_002"`
- final `chat/turn`: no tool call and non-empty narrative
- turn log has at least 6 rows for the full chain
