# Item Runtime Model

## Inventory Authority

- `campaign.items` is the source of truth for portable item state.
- `actors[*].inventory` is a derived compatibility view.
- Portable item persistence belongs in stacks, not in scene entities.

## Acquisition Flow

- Mainline acquisition is `search -> reveal -> take`.
- `search` reveals or discovers stack-backed loot and may return a no-op when nothing is available.
- `take` is required for possession; search alone does not move ownership to the actor.
- Settled playable paths (`test_watchtower_world` and derived `key_gate_scenario`) follow this model.

## Gate Checks

- Gated movement still uses `required_item_id` rules.
- Possession evidence comes from actor-owned stacks derived from `campaign.items`.
- Settled playable content no longer duplicates gate requirements onto scene entities as authoritative state.

## Legacy: inventory_add

Purpose:
- Keep the existing turn/tool contract for narrated inventory gain that still depends on authoritative source entities.

Required args:
- `item_id`
- `source_entity_id`
- `quantity` defaults to `1` and must be `> 0`

Source-entity schema:
- `state.inventory_item_id`
- `state.inventory_quantity`
- `state.inventory_granted`

Behavior:
- validates the source entity
- grants an actor-owned stack through the runtime item layer
- marks the source entity as consumed

Scope:
- legacy-only contract
- not part of mainline search/reveal/take gameplay

## Related Docs

- `docs/20_runtime/storage_authority.md`
- `docs/01_specs/tools.md`
- `docs/20_runtime/testing/test_watchtower_world_manual_test.md`
