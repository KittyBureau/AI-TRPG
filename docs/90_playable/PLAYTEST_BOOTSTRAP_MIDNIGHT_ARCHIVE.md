# Playtest Bootstrap: Midnight Archive

Temporary guide. Local only. One scenario only.

## 1. Quick Start (TL;DR)

From repo root:

```powershell
uvicorn backend.api.main:app --reload
```

If runtime says `passphrase_required`:

```powershell
python -m backend.tools.unlock_keyring
```

Then:

1. Confirm `midnight_archive_world` is listed.
2. Create a campaign with that world.
3. Play with:
   - API: `POST /api/v1/chat/turn`
   - optional UI: `frontend/play.html`

API base:

```powershell
$BASE = "http://127.0.0.1:8000"
```

## 2. Backend Startup

Working directory:

```powershell
cd E:\202410\Repos\AI-TRPG
```

Start backend:

```powershell
uvicorn backend.api.main:app --reload
```

Expected success signal:

- terminal shows Uvicorn startup
- server listens on `http://127.0.0.1:8000`
- `http://127.0.0.1:8000/api/v1/docs` opens

Readiness check:

```powershell
Invoke-RestMethod "$BASE/api/v1/runtime/status"
```

Expected:

- `ready = true`

If not ready:

```powershell
python -m backend.tools.unlock_keyring
```

## 3. Scenario Preparation

`Midnight Archive` is now a real built-in preset world.

World id:

```text
midnight_archive_world
```

Availability check:

```powershell
Invoke-RestMethod "$BASE/api/v1/worlds/list" | Where-Object { $_.world_id -eq "midnight_archive_world" }
```

Expected:

- one row with:
  - `world_id = midnight_archive_world`
  - `name = Midnight Archive`

## 4. Campaign Bootstrap

### Option A - API

Create campaign:

```powershell
$Create = Invoke-RestMethod `
  -Method Post `
  -Uri "$BASE/api/v1/campaign/create" `
  -ContentType "application/json" `
  -Body (@{
    world_id = "midnight_archive_world"
    party_character_ids = @("pc_001")
    active_actor_id = "pc_001"
  } | ConvertTo-Json)

$CampaignId = $Create.campaign_id
$CampaignId
```

Expected response fields:

- `campaign_id`

Quick check:

```powershell
Invoke-RestMethod "$BASE/api/v1/campaign/get?campaign_id=$CampaignId"
Invoke-RestMethod "$BASE/api/v1/map/view?campaign_id=$CampaignId&actor_id=pc_001"
```

Expected:

- current area is `Street Gate`
- objective mentions the restricted archive
- `Night Porter` is visible in current area entities

### Option B - Frontend

Start static server:

```powershell
cd frontend
python -m http.server 5173
```

Open:

- `http://127.0.0.1:5173/play.html`

Then:

1. Set Base URL to `http://127.0.0.1:8000`
2. In `Campaign Panel`, create/select a campaign using `midnight_archive_world`
3. Refresh campaign
4. Use `Actor Control Panel` to send turns

Raw request/response page:

- `http://127.0.0.1:5173/debug.html`

## 5. How to Play (Core Loop)

Send a turn:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "$BASE/api/v1/chat/turn" `
  -ContentType "application/json" `
  -Body (@{
    campaign_id = $CampaignId
    user_input = "Talk to the night porter about the inspection records."
    execution = @{ actor_id = "pc_001" }
  } | ConvertTo-Json -Depth 10)
```

Read these fields:

- `narrative_text`
- `applied_actions`
- `state_summary.active_area_name`
- `state_summary.active_actor_inventory`

Check current scene:

```powershell
Invoke-RestMethod "$BASE/api/v1/map/view?campaign_id=$CampaignId&actor_id=pc_001"
```

Use:

- `current_area`
- `reachable_areas`
- `entities_in_area`

Good example inputs:

- `Talk to the night porter about the inspection records.`
- `Inspect the notice board.`
- `Search the lost-and-found tray.`
- `Talk to the assistant archivist.`
- `Search the returns cart for routing paperwork.`
- `Open the desk safe.`

## 6. Required Test Paths

### Path 1 - Official Route

Goal: validate pass -> office -> key -> official archive entry.

High-level steps:

1. Reach `Lobby`
2. Search `Lost-and-Found Tray`
3. Take `Office Pass`
4. Enter `Clerk Office`
5. Open/search `Desk Safe`
6. Take `Archive Key`
7. Reach `Storage Room`
8. Enter `Restricted Archive`

Expected:

- entering `Clerk Office` fails before the pass
- entering `Restricted Archive` from `Storage Room` fails before the key

### Path 2 - Service Route

Goal: validate info-driven bypass without `archive_key`.

How player discovers it:

1. Talk to `Assistant Archivist`
2. Search `Returns Cart`
3. Find `Routing Slip`

Key steps:

1. Reach `Reading Room`
2. Get `Routing Slip`
3. Move to `Returns Annex`
4. Inspect `Document Lift`
5. Enter `Restricted Archive` from the annex side

Expected:

- player reaches the archive without `Archive Key`
- player never needs `Clerk Office`

### Path 3 - Chaotic Play

Goal: see whether the scenario recovers when the player plays badly.

Do this on purpose:

1. Ignore NPCs at first
2. Wander between areas
3. Repeat searches on already-used objects
4. Try the official archive door too early
5. Recover later through either route

Expected:

- no hard deadlock
- repeated actions feel less useful
- route distinction still becomes visible

## 7. What to Observe

Checklist:

- Did the player notice there were two routes?
- Did information change what the player chose next?
- Did it still feel like a pure key-door loop?
- Did the player get stuck?
- Did the player accidentally bypass the intended experience too early?
- Did the service route feel discovered, not random?

## 8. Known Pitfalls

- Player skips NPCs and brute-forces searches.
- Player guesses the service route from area names.
- Player keeps retrying the official archive door without the key.
- Player expects repeated search targets to produce new loot.
- LLM may over-explain the alternate route if prompted too directly.

## 9. Minimal Debug Tips

Inspect current map view:

```powershell
Invoke-RestMethod "$BASE/api/v1/map/view?campaign_id=$CampaignId&actor_id=pc_001"
```

Inspect full campaign state:

```powershell
Invoke-RestMethod "$BASE/api/v1/campaign/get?campaign_id=$CampaignId"
```

If stuck, check:

1. Is the actor in the area you think they are?
2. Is `Office Pass`, `Archive Key`, or `Routing Slip` actually in inventory?
3. Was the clue source already searched once?
4. Are you trying `Storage Room -> Restricted Archive` without `Archive Key`?
5. Are you standing in `Returns Annex` before trying the bypass route?

Last-resort local check:

```powershell
Get-Content "storage/campaigns/$CampaignId/campaign.json" -Raw
```
