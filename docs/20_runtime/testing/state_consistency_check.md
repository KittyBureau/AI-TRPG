# State Consistency Check (Play)

## Purpose

Use this guide to verify Play panel state remains aligned with backend campaign persistence after actor/party mutations.

## What `refreshCampaign` Does

`refreshCampaign` performs a backend-authoritative read via:

- `GET /api/v1/campaign/get?campaign_id=<id>`

It rewrites frontend state from response `selected`:

- `state.campaign.party_character_ids`
- `state.campaign.active_actor_id`
- `state.campaign.status`

No local party repair is performed beyond lightweight normalization (trim empty values, dedupe).

## Auto Refresh Triggers

The Play flow now triggers `refreshCampaign` automatically after these successful actions:

- `loadCharacterToCampaign`
- `selectActiveActor`
- `chatTurn` actions in Actor Control (`Send Turn`, `Move`)

This keeps Party/Active display and next action actor resolution consistent with persisted `campaign.json`.

## Recommended Debug Flow

1. Select or create a campaign in Play.
2. Load one or more library characters to campaign.
3. Switch active actor in Party panel.
4. Execute `Move` or `Send Turn` in Actor Control.
5. Click `Refresh Campaign` manually to force deterministic re-sync.
6. Verify:
   - Party panel equals backend `selected.party_character_ids`
   - Active actor equals backend `selected.active_actor_id`
   - Campaign panel lifecycle/milestone display equals backend `status`
   - Actor Control `Acting as` follows `resolveActingActorId(state)`

## Failure Diagnosis

- If `refreshCampaign` fails, check Network:
  - endpoint reachable (`/api/v1/campaign/get`)
  - request `campaign_id` is non-empty
  - response contains `selected.party_character_ids` and `selected.active_actor_id`
- expected failure semantics:
  - missing campaign -> `404`
  - invalid persisted campaign payload -> `500`
- on refresh failure, Play store should keep the previous party/active snapshot instead of rewriting local state from a partial payload
- on refresh failure, Play store should clear campaign status display instead of showing stale status for the wrong campaign snapshot
- If active switch fails:
  - ensure target actor is in `party_character_ids` (backend validation rejects otherwise)
