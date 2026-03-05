# Active Actor Integration Smoke (Play Panels)

## Scope

This smoke guide verifies only the `play.html` panel architecture:

- Campaign Panel
- Character Library Panel
- Party Panel
- Actor Control Panel
- Debug Panel

Out of scope for this smoke: `frontend/debug.html` + `frontend/debug.js` and deprecated `frontend/index.html`.

## Preconditions

1. Backend is running (example: `http://127.0.0.1:8000`).
2. Frontend static server is running (example: `http://127.0.0.1:5173/play.html`).
3. Open browser devtools Network tab.

## Target Flow

1. Create or select campaign
2. Create library character
3. Load character to campaign
4. Set active actor
5. Move
6. Turn
7. Refresh page and verify consistency

## Step-by-step

### 1) Create/Select Campaign

- In **Campaign Panel**, set Base URL.
- Click `Refresh` and select an existing campaign, or click `Create Campaign`.

Expected request:

- `GET /api/v1/campaign/list`
- optional: `POST /api/v1/campaign/create`

Expected state/UI:

- `state.campaignId` is set.
- Campaign dropdown shows `active=...`.

### 2) Create Library Character

- In **Character Library Panel**, fill `Name` (and optional `Summary`, `Tags`), click `Create`.

Expected request:

- `POST /api/v1/characters/library`
- then `GET /api/v1/characters/library` (refresh list)

Expected state/UI:

- `state.character.library` includes the new entry.
- list renders new character row.

### 3) Load Character to Campaign

- In character row, click `Load to Campaign`.
- Repeat for at least 2 characters so party has multiple actors.

Expected request:

- `POST /api/v1/campaigns/{campaign_id}/party/load`

Expected state/UI:

- `state.campaign.party_character_ids` contains loaded character ids.
- `state.campaign.active_actor_id`:
  - set only if previous active is empty
  - unchanged otherwise
- **Party Panel** shows updated `party_character_ids`.

Campaign persistence expectation:

- `campaign.json.selected.party_character_ids` appended.
- `campaign.json.actors[character_id]` exists.

### 4) Set Active Actor

- In **Party Panel**, select a different actor and click `Set Active`.

Expected request:

- `POST /api/v1/campaign/select_actor`
- body contains `campaign_id` and `active_actor_id`

Expected state/UI:

- `state.campaign.active_actor_id` updates to selected actor.
- Party panel line `active_actor_id: ...` updates.
- Actor Control line `Acting as: ...` updates to the same actor.
- Actor Control actor dropdown value matches new active actor.

Campaign persistence expectation:

- `campaign.json.selected.active_actor_id` equals selected actor.

### 5) Move

- In **Actor Control Panel**, enter `to_area_id`.
- Click `Move`.

Expected request:

- `POST /api/v1/chat/turn`
- payload includes:
  - `campaign_id`
  - `execution.actor_id == "Acting as"` actor
  - move tool instruction with matching `args.actor_id`

Expected state/UI:

- status shows `Move completed as <actor_id>.`
- no mismatch between displayed `Acting as` and request `execution.actor_id`.

### 6) Turn

- In **Actor Control Panel**, enter turn text and click `Send Turn`.

Expected request:

- `POST /api/v1/chat/turn`
- payload includes:
  - `campaign_id`
  - `execution.actor_id == "Acting as"` actor

Expected state/UI:

- status shows `Turn completed as <actor_id>.`
- no mismatch between displayed `Acting as` and request `execution.actor_id`.

### 7) Refresh Campaign Consistency

- In **Campaign Panel**, click `Refresh Campaign`.

Expected request:

- `GET /api/v1/campaign/get?campaign_id=...`

Expected state/UI (authoritative from backend):

- Party panel shows latest `active_actor_id`.
- Party panel shows latest `party_character_ids`.
- Actor Control resolves `Acting as` by rule:
  - use `state.campaign.active_actor_id` when it is in party
  - otherwise fallback to first party actor
  - if party empty: `Acting as: none`, Turn/Move buttons disabled

## Pass Criteria

1. After Party Panel switch, Actor Control `Acting as` changes to same actor.
2. Move/Turn requests always use `execution.actor_id` equal to displayed `Acting as`.
3. No state where Party shows one active actor while Actor Control acts with another.
4. When party is empty, Actor Control shows `Party empty / no actor selected` and disables action buttons.
