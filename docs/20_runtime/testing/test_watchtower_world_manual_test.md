# Test Watchtower World Manual Test

Last updated: 2026-03-11

This guide verifies the fixed smoke-test world `test_watchtower_world` through the existing Play flow.
Use it as the reusable watchtower regression scenario for smoke retests.
It is also the source behavior reference for `key_gate_scenario` Scenario Template 0 design work.

## Scope

- fixed world loading
- campaign creation from a selected world
- single active actor spawn at the configured start area
- area movement and area context
- one NPC hint source
- one key-item acquisition
- inventory visibility during play
- one simple item gate
- objective completion by entering the target area

## Preconditions

1. Backend is running.
2. Frontend Play page is available.
3. `test_watchtower_world` is visible in the world list as a built-in preset.
4. Create or select exactly one playable actor for this smoke.

## Recommended Steps

### 1. Confirm the world exists

- In `World Panel`, refresh worlds.
- Confirm `test_watchtower_world` is listed.

Expected:

- world list includes `Test Watchtower World`
- `World Preview` later shows:
  - `world_id = test_watchtower_world`
  - `start_area = village_gate`
  - objective text about finding the key and entering the watchtower
  - the preset remains available without any committed `storage/worlds/**` file

### 2. Create a campaign bound to the world

- In `Campaign Panel`, use `Create With Selected Party`.
- Choose exactly one character.
- Select `test_watchtower_world` as `Existing World`.

Expected:

- campaign is created successfully
- after refresh, `World Preview` shows the watchtower world metadata
- `Campaign Panel` remains `Status: active`

### 3. Verify start area

- Check `Map Panel`.

Expected:

- active actor is the selected character
- current area is `Village Gate (village_gate)`
- reachable areas include `Village Square (village_square)`

### 4. Talk to the guard

- In `Actor Control`, send a turn such as `Talk to the village guard about the watchtower key.`

Expected:

- latest turn applies `scene_action`
- response/narrative explicitly points you to the old hut
- current area remains `village_gate`

### 5. Move to the hut

- Move to `village_square`
- Move to `old_hut`

Expected:

- each move updates `Map Panel` current area
- `old_hut` area description is visible in `Map Panel`

### 6. Search for the key

- In `Actor Control`, send a turn such as `Search the loose floorboard in the old hut.`

Expected:

- latest turn applies `scene_action`
- response/narrative says the search finds `tower_key`
- `Actor Control` inventory shows `tower_key x1`
- repeating the same clue interaction does not increase the count beyond `x1`

### 7. Approach the watchtower

- Move from `old_hut` to `village_square`
- Move to `forest_path`
- Move to `watchtower_entrance`

Expected:

- `Map Panel` current area becomes `Watchtower Entrance (watchtower_entrance)`
- reachable areas still show the tower interior route

### 8. Enter the watchtower

- With `tower_key` already in inventory, move to `watchtower_inside`

Expected:

- move succeeds
- current area becomes `Watchtower Interior (watchtower_inside)`
- latest turn shows a successful `move`

### 9. Verify objective completion

- Refresh the campaign if needed.
- Check `Campaign Panel` and the latest turn result/debug output.

Expected:

- campaign status changes to `ended`
- ended reason is `goal_achieved`
- latest authoritative area remains `watchtower_inside`

## Verified Regression Outcome

- Manual verification on 2026-03-11 passed for the full fixed watchtower loop.
- Reuse this scenario when checking inventory authority, one-time clue grants, locked-area gating, and goal completion regressions.

## Failure Cues

- If entering `watchtower_inside` fails before the key is found, that is expected gate behavior.
- If the key is narrated as found but inventory does not show `tower_key`, treat it as a failure.
- If the final move succeeds but campaign status does not end with `goal_achieved`, treat it as a failure.
