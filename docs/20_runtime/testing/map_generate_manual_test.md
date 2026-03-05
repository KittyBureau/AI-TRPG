# Map Generate Manual Smoke (Non-deterministic)

## Goal

Validate `map_generate` behavior under real `/api/v1/chat/turn` execution where model output may vary.

This is a manual smoke/regression guide, not a strict deterministic CI test.

## Scope

- Entry endpoint: `POST /api/v1/chat/turn`
- Focus: tool-chain safety and storage authority integrity
- Not in scope: exact narrative wording

## Pass Criteria

1. Success case:
   - `applied_actions[*].tool` contains `map_generate`
   - map data persists in `campaign.json.map`
2. Rejection/failure case:
   - no unintended map mutation
   - failure reason is returned via `tool_feedback.failed_calls[*]`
3. Authority checks:
   - adjacency authority is `map.areas[*].reachable_area_ids`
   - `map.connections` is derived index and can differ in order only
   - actor position authority remains `actors[*].position`
   - legacy mirrors (`state.positions*`) are non-authoritative

## Preconditions

1. Backend running at `http://127.0.0.1:8000`
2. Campaign exists (`POST /api/v1/campaign/create`)
3. Optional: enable trace for easier resource/debug observation

## Suggested Steps

1. Create campaign
2. Run one turn that requests map generation (direct instruction or `UI_FLOW_STEP` template)
3. Check response fields:
   - `tool_calls`
   - `applied_actions`
   - `tool_feedback`
   - `state_summary`
4. Inspect storage:
   - `storage/campaigns/<campaign_id>/campaign.json`
   - verify `map.areas` and `map.connections`
5. Run a negative case (invalid args/constraints) and confirm no destructive map mutation

## Optional Deterministic Alternative

For deterministic coverage, prefer:

- `scripts/smoke_full_gameplay.ps1`
- `backend/tests/test_map_generate.py`
