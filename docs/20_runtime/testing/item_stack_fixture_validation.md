# Item Stack Fixture Validation

Tracked fixture source:

- `backend/tests/fixtures/campaigns/camp_item_stack_fixture/campaign.json`

Runtime working copy for manual validation:

- copy the tracked fixture to `storage/campaigns/camp_item_stack_fixture/campaign.json`

Purpose:

- provide one isolated stack-first baseline for manual runtime validation
- seed item authority through `campaign.items`
- keep aggregate inventory passive so fallback-to-legacy behavior is obvious

Initial expected raw fixture state:

- active actor: `ch_e3cd4e96`
- active area: `area_start`
- `actors.ch_e3cd4e96.inventory` is intentionally `{}` in the tracked fixture file
- authoritative stacks live under `campaign.items`
- seeded stacks:
  - `stk_fixture_tonic_actor` -> actor-held `healing_tonic` quantity `2`
  - `stk_fixture_ration_actor` -> actor-held `field_ration` quantity `1`
  - `stk_fixture_torch_ground_start` -> area-held `torch` quantity `1` in `area_start`
  - `stk_fixture_rope_remote` -> area-held `rope` quantity `1` in `area_gate`

Expected runtime/load normalization:

- loading the campaign may populate derived compatibility inventory for the actor
- that derived mirror should become:
  - `healing_tonic: 2`
  - `field_ration: 1`
- the source of truth must remain the four stack records in `campaign.items`

Manual validation flow:

1. Copy `backend/tests/fixtures/campaigns/camp_item_stack_fixture/campaign.json` to `storage/campaigns/camp_item_stack_fixture/campaign.json`.
2. Load the campaign and inspect the runtime working copy under `storage/campaigns/camp_item_stack_fixture/campaign.json`.
3. Call `GET /api/v1/campaign/get?campaign_id=camp_item_stack_fixture`.
4. Confirm `inventory_stacks` contains the actor-held tonic/ration stacks and the compatibility actor inventory is derived, not independently seeded.
5. Use `GET /api/v1/map/view?campaign_id=camp_item_stack_fixture&actor_id=ch_e3cd4e96` to inspect the ground torch in `area_start`.
6. Run a `take` against `stk_fixture_torch_ground_start`.
7. Confirm the torch stack parent changes from `area_start` to actor `ch_e3cd4e96`.
8. Run a `drop` against `stk_fixture_ration_actor`.
9. Confirm the ration stack parent changes from actor `ch_e3cd4e96` to the actor's current area.
10. Run a `use` against `stk_fixture_tonic_actor`.
11. Confirm tonic quantity decreases and the stack is deleted when quantity reaches zero.

Persistence checks:

- inspect `storage/campaigns/camp_item_stack_fixture/campaign.json`
- inspect `storage/campaigns/camp_item_stack_fixture/turn_log.jsonl` if turns were executed
- inspect `/api/v1/campaign/get`
- inspect turn `state_summary.inventory_stacks` and `state_summary.active_actor_inventory_stacks`
- inspect Play/Debug raw output for `selected_stack_id`, selection audit, and stack snapshots

Evidence of accidental fallback to legacy aggregate authority:

- an item appears usable/takeable/droppable without a matching stack in `campaign.items`
- `actors[*].inventory` changes while the relevant stack parent/quantity does not
- `inventory_stacks` and persisted `campaign.items` disagree on ownership or quantity
- item behavior depends on seeding aggregate inventory counts rather than stack records

Primary files and outputs to inspect:

- `backend/tests/fixtures/campaigns/camp_item_stack_fixture/campaign.json`
- `storage/campaigns/camp_item_stack_fixture/campaign.json`
- `storage/campaigns/camp_item_stack_fixture/turn_log.jsonl`
- `/api/v1/campaign/get`
- `/api/v1/map/view`
- `/api/v1/chat/turn`
- Play Debug panel / raw response viewer
