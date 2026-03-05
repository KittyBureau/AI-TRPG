# Full Gameplay Smoke Test

## Purpose

Provide a deterministic, regression-friendly gameplay loop test for the MVP path without changing business implementation.

Fixed chain:

1. `create_campaign`
2. `world_generate`
3. `map_generate`
4. `actor_spawn`
5. `move_options`
6. `move`
7. one narrative-only `chat/turn`

## Files

- `scripts/smoke_full_gameplay.ps1`
- `scripts/smoke_full_gameplay_server.py`
- `backend/tests/test_full_gameplay_loop.py`

## Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1
```

Keep workspace:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1 -KeepWorkspace
```

Pytest integration:

```powershell
python -m pytest backend/tests/test_full_gameplay_loop.py -q
```

## Workspace

Default per-run workspace:

- `.tmp/smoke_full_gameplay/<run_id>`

Artifacts:

- `storage/campaigns/<campaign_id>/campaign.json`
- `storage/campaigns/<campaign_id>/turn_log.jsonl`
- `storage/worlds/<world_id>/world.json`

## PASS/FAIL Contract

Script output includes:

- per-step `PASS`/`FAIL`
- summary line `Result: PASS` or `Result: FAIL`
- failure location hint format:
  - `定位: <step> -> <field> -> <file>:<line> | <message>`

Example:

- `定位: move -> actors.pc_001.position -> .../campaign.json:123 | pc_001 position mismatch`

## Key Assertions

- world persistence and campaign binding are valid
- map generated area ids persist under `campaign.map.areas`
- spawned actor persists and joins party list
- `actors.pc_001.position == "area_002"` after move
- final narrative-only turn has no applied tool action and non-empty text
- turn log has at least 6 rows
