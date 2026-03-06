# Playable v1 Manual Test

Last updated: 2026-03-05

This guide provides repeatable manual verification for Playable v1.

## Test Set A: Deterministic Regression (Primary)

Use existing smoke scripts first. This is the required baseline.

### A1. Full gameplay deterministic smoke

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1
```

Optional artifact retention:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1 -KeepWorkspace
```

Expected observations:

- script summary shows `PASS`
- applied chain is present:
  - `world_generate`
  - `map_generate`
  - `actor_spawn`
  - `move_options`
  - `move`
  - final narrative-only chat turn
- storage artifacts exist:
  - `storage/campaigns/<campaign_id>/campaign.json`
  - `storage/campaigns/<campaign_id>/turn_log.jsonl`
  - `storage/worlds/<world_id>/world.json`
- persistence checks pass:
  - `actors.<spawned_actor_id>` exists
  - `actors.pc_001.position == "area_002"`

### A2. Frontend flow deterministic smoke

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1
```

Optional retry/artifacts:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1 -RetryAttempts 3 -KeepWorkspace
```

Expected observations:

- script summary shows `PASS`
- tool-chain protocol success under `/api/v1/chat/turn`:
  - `world_generate`
  - `map_generate`
  - `actor_spawn`
  - `move`
- final narrative-only turn contains:
  - `narrative_text`
  - `state_summary`
  - no applied actions

### A3. World generate deterministic smoke (optional but recommended)

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1
```

Expected observations:

- Case A: unbound empty world id returns `world_id_missing`
- Case B: explicit world id creates world file
- Case C: repeated same world id keeps deterministic seed/generator
- Case D: `bind_to_campaign=true` persists and later reuse works

## Test Set B: LLM 10-turn Playthrough (Supplementary)

This complements deterministic scripts with real model behavior checks.

### B0. Preconditions

- backend running (`uvicorn backend.api.main:app --reload`)
- `storage/config/llm_config.json` configured
- frontend static server (if testing via UI)

### B1. Trace gate default-off check

1. Create campaign (`POST /api/v1/campaign/create`).
2. Submit one turn (`POST /api/v1/chat/turn`).
3. Confirm response has no top-level `debug` field.

Expected observation:

- trace is off by default (`dialog.turn_profile_trace_enabled=false`).

### B2. Optional trace-on check

Enable trace:

```json
POST /api/v1/settings/apply
{
  "campaign_id": "camp_0001",
  "patch": {
    "dialog.turn_profile_trace_enabled": true
  }
}
```

Then submit one turn and observe:

- response includes `debug.resources`
- `debug.resources` has arrays:
  - `prompts`, `flows`, `schemas`, `templates`, `policies`, `template_usage`

### B3. 10-turn execution loop

Run from zero state to 10 turns (API or `frontend/play.html`):

1. create campaign
2. ensure world exists (`world_generate` in turn)
3. generate/expand map (`map_generate`)
4. spawn/load at least one additional actor
5. perform movement attempts (`move` / `move_options`)
6. perform one scene interaction (`scene_action`)
7. perform one inventory change (`inventory_add`)
8. continue normal narrative turns until total turn count reaches 10

Per-turn expected observations:

- response includes required keys:
  - `effective_actor_id`, `narrative_text`, `dialog_type`, `state_summary`
- if tool is intended, corresponding `applied_actions[*].tool` is present
- actor mismatch requests are rejected with `actor_context_mismatch`
- no impossible state jumps in storage (`actors` is authority)

### B4. Pass / Fail criteria

Pass:

- 10 turns completed without server crash
- `turn_log.jsonl` has >=10 entries for campaign
- storage remains parseable JSON and actor authority fields are coherent
- deterministic smoke suite (Set A) remains green

Fail:

- API 500 errors during normal flow
- tool execution mutates wrong actor/state unexpectedly
- storage corruption or missing required campaign/turn/world files

### B5. Record template

Use this minimal record block during each release-candidate run:

```text
Set B Run Record
- Date:
- Operator:
- Backend mode: real LLM / controlled stub
- Campaign id:
- Trace off check: PASS / FAIL
- Trace on check (optional): PASS / FAIL / SKIPPED
- Turns completed:
- Tools observed:
  - world_generate:
  - map_generate:
  - move_options:
  - move:
  - scene_action:
  - inventory_add:
  - narrative-only turn:
- turn_log.jsonl row count:
- Storage parseable: PASS / FAIL
- Actor authority coherent: PASS / FAIL
- Notes / blockers:
```

## Recommended Logging During Manual Runs

Capture:

- request payload (or UI action)
- response excerpt (`tool_calls`, `applied_actions`, `tool_feedback`, `state_summary`)
- file delta checks for `campaign.json` and `turn_log.jsonl`
