# Item System v2 Spec

Status: design freeze for the item-system refactor track.

Date: 2026-03-13.

Scope of this document:

- This is a repository-grounded design spec only.
- It does not change current runtime behavior by itself.
- Current code remains authoritative until implementation lands.
- This spec defines the target authority model and the phased migration path.

## 1. Current-System Audit

### 1.1 Current runtime storage split

Current code has two separate runtime item authorities.

| Concern | Current authority | Repo evidence | Notes |
| --- | --- | --- | --- |
| Actor-held item counts | `campaign.actors[*].inventory` | `backend/domain/models.py`, `backend/app/turn_service.py`, `backend/api/routes/campaign.py` | Stored as `Dict[str, int]`, keyed by `item_id` only. |
| Portable scene-object location | `campaign.entities[*].loc` | `backend/domain/models.py`, `backend/app/tool_executor.py`, `backend/app/scene_entities.py`, `backend/api/routes/map.py` | Stored as full `Entity` objects with `loc.type in {area, actor, entity}`. |
| Item grants from searchable sources | `campaign.entities[*].state.inventory_*` plus `actors[*].inventory` mutation | `backend/app/tool_executor.py`, `backend/app/world_presets.py`, `backend/app/scenario_runtime_mapper.py` | Searchable entities grant counts directly into actor inventory. |
| Selected item context | Frontend-only per-actor `item_id`, validated against `actors[*].inventory` | `frontend/store/store.js`, `frontend/panels/actor_control_panel.js`, `backend/api/routes/chat.py`, `backend/app/turn_service.py` | No stack identity exists. |

The result is not a single runtime item model. The repo currently has:

- count-based inventory authority for actor possession
- entity-location authority for portable world objects
- entity-state authority for item sources and gate requirements

Current docs also still reflect that live code state:

- `docs/20_runtime/storage_authority.md`
- `docs/01_specs/storage_layout.md`

Those docs remain accurate for the current implementation. This spec defines the replacement target, not current runtime truth.

### 1.2 Current model definitions

`backend/domain/models.py` defines:

- `ActorState.inventory: Dict[str, int]`
- `Campaign.entities: Dict[str, Entity]`
- `EntityLocation.type: Literal["area", "actor", "entity"]`

There is no `campaign.items` collection today.

There is also no existing stack identifier model, no `definition_id` / `stack_id` split, and no runtime item schema independent from `Entity`.

### 1.3 How `actors[*].inventory` currently works

Current inventory behavior is count-only and actor-scoped.

Relevant code:

- `backend/domain/state_utils.py`
  - normalizes `ActorState.inventory` to positive integer counts keyed by non-empty strings
- `backend/app/tool_executor.py`
  - `_grant_inventory_from_source(...)` is the only runtime write path in app code that increments `actor.inventory`
  - `_apply_inventory_add(...)` delegates to `_grant_inventory_from_source(...)`
- `backend/app/turn_service.py`
  - `_active_actor_inventory(...)` reads `actor.inventory`
  - `_all_actor_inventories(...)` derives state summary from `actor.inventory`
- `backend/api/routes/campaign.py`
  - `campaign/get` serializes `actors[*].inventory`

Important current properties:

- inventory keys are plain `item_id`
- no per-instance identity exists
- no parent/container relation exists inside inventory
- no per-stack metadata exists beyond optional catalog lookup by `item_id`
- move gating uses aggregated counts, not runtime item instances

### 1.4 How `campaign.entities` currently participates in portable/world item behavior

`campaign.entities` currently mixes fixed scene objects, NPCs, portable objects, containers, and nested portable contents.

Relevant code:

- `backend/app/tool_executor.py`
  - `scene_action take` moves an entity to `EntityLocation(type="actor", id=actor_id)`
  - `scene_action drop` moves an entity to `EntityLocation(type="area", id=current_area_id)`
  - `scene_action detach` mutates a fixed object into `kind="item"` and moves it to the actor
  - `scene_action use` validates `params.item_id` by looking up `campaign.entities[item_id]` in actor inventory location
  - `_resolve_root_location(...)` walks `EntityLocation(type="entity")` parent chains for reachability
  - `_actor_inventory_mass(...)` computes carry mass from actor-held portable entities in `campaign.entities`
- `backend/app/scene_entities.py`
  - area display currently lists only entities whose `loc.type == "area"` and `loc.id == area_id`
- `backend/api/routes/map.py`
  - `map/view` uses `build_area_local_entity_views(...)`

Current consequences:

- a portable entity can be in an actor inventory location without appearing in `actors[*].inventory`
- nested container contents can exist as `loc.type == "entity"` without any inventory count representation
- map area display only shows direct area entities, not nested entity children or actor-held portable entities

### 1.5 Current split-authority failure case

The repo already contains the split in live behavior:

- `inventory_add` / search-based grants mutate `actors[*].inventory` but do not create a portable runtime object
- `take` / `drop` / `detach` mutate `campaign.entities[*].loc` but do not update `actors[*].inventory`

This is directly visible in:

- `backend/app/tool_executor.py`
- `backend/tests/test_scene_action_tool.py`
  - `take` / `drop` changes entity location while existing `actors["pc_001"].inventory` remains unchanged
- `backend/tests/test_inventory_add_tool.py`
  - inventory gain updates `actors[*].inventory` through authoritative source entities

### 1.6 Current searchable source and gate coupling

Scenario and preset content currently encode item gameplay in entity state:

- `inventory_item_id`
- `inventory_quantity`
- `inventory_granted`
- `required_item_id`

Repo evidence:

- `backend/app/world_presets.py`
- `backend/app/scenario_runtime_mapper.py`
- `backend/app/tool_executor.py`

This means some item behavior is embedded in fixed `campaign.entities` instead of a dedicated runtime item collection.

### 1.7 Current selected item behavior

Current selected-item flow:

1. Frontend stores per-actor `selectedItemIdByActor` keyed by plain `item_id`.
2. `frontend/panels/actor_control_panel.js` sends `context_hints.selected_item_id`.
3. `backend/api/routes/chat.py` forwards `selected_item_id` into `TurnService.submit_turn(...)`.
4. `backend/app/turn_service.py::_resolve_selected_item_context(...)` validates the id against `actors[effective_actor_id].inventory`.
5. If valid, prompt context gets:
   - `{ id, quantity }`
   - plus optional `{ name, description }` from `resources/data/items_catalog_v1.json`
6. If trace is enabled, `debug.selected_item = { id, has_metadata }`.

Important current properties:

- selection is request-scoped, not campaign-persisted
- selection is frontend-owned, not backend-owned
- validation is against aggregated actor inventory only
- invalid selections are silently ignored, not stored or repaired by backend

### 1.8 Current frontend/store assumptions

Current frontend assumptions are hard-coupled to aggregated `item_id -> quantity` inventory shape.

Repo evidence:

- `frontend/store/store.js`
  - `inventoryByActor`
  - `selectedItemIdByActor`
  - `normalizeInventory(...)`
  - `normalizeCampaignInventories(...)`
  - `recordTurnResult(...)` reads `state_summary.inventories` or `state_summary.active_actor_inventory`
  - `refreshCampaign(...)` seeds inventory from `campaign/get.actors[*].inventory`
- `frontend/utils/inventory_items.js`
  - expects `{ item_id: quantity }`
  - builds UI rows keyed by `item_id`
- `frontend/panels/actor_control_panel.js`
  - selection toggles by `item.item_id`
  - request hint sends `selected_item_id`
  - UI text shows `item_id`
- `frontend/app.js`
  - old debug console renders `state_summary.active_actor_inventory`
- `frontend/renderers/delta_renderer.js`
  - computes inventory delta from aggregated `state_summary.inventories`

### 1.9 Current tests covering item-related behavior

Direct backend coverage:

- `backend/tests/test_inventory_add_tool.py`
- `backend/tests/test_scene_action_tool.py`
- `backend/tests/test_scene_action_turn_api.py`
- `backend/tests/test_map_view_scene_entities.py`
- `backend/tests/test_turn_selected_item_context.py`
- `backend/tests/test_turn_response_contract_api.py`
- `backend/tests/test_turn_execution_actor_context.py`
- `backend/tests/test_move.py`
- `backend/tests/test_watchtower_world.py`
- `backend/tests/test_watchtower_world_turn_api.py`
- `backend/tests/test_scenario_runtime_integration.py`
- `backend/tests/test_world_api.py`
- `backend/tests/test_campaign_get_api.py`
- `backend/tests/test_campaign_get_endpoint.py`

Adjacent preservation coverage:

- `backend/tests/test_character_library_api.py`
- `backend/tests/test_character_fact_api.py`

Frontend coverage:

- `frontend/tests/store_loop.test.mjs`
- `frontend/tests/inventory_items.test.mjs`

### 1.10 Current repo constraints that matter for v2

The audit found three constraints that materially shape the v2 design.

1. The repo has only a lightweight catalog at `resources/data/items_catalog_v1.json`.
   - It stores only `name` and `description`.
   - There is no rich existing global item-definition registry for all portable runtime objects.
2. Containers already exist, but only through `campaign.entities` parent chains.
   - Reachability currently supports shallow nested `entity -> entity -> area/actor` paths.
3. Area display currently only shows direct area children.
   - `map/view` and prompt `scene.entities_in_area` do not resolve nested item contents.

These constraints mean Item System v2 must:

- not assume a rich external definition database already exists
- explicitly handle container parent chains
- provide a thin location/visibility helper even if first-phase display remains conservative

## 2. Problem Statement

The current split model is now the main blocker for item-system growth.

Current limitations:

- The engine has no single authoritative runtime representation for portable items.
- The same gameplay concept can live either as:
  - an aggregated count in `actors[*].inventory`
  - a portable entity in `campaign.entities`
  - entity state on a searchable source or gate
- `take` / `drop` and `inventory_add` do not operate on the same runtime object.
- Containers exist only for entity-based portable objects, not for inventory items.
- Selected-item context is keyed by plain `item_id`, so it cannot distinguish stacks or instances.
- Searchable clue sources can grant an item without any runtime item object ever existing in the world.
- Move gating, prompt context, API responses, and frontend selection all read aggregated inventory counts instead of runtime item instances.

This is already producing concept drift:

- possession can mean either `actor.inventory[item_id] > 0` or `entity.loc.type == "actor"`
- portability can exist without inventory counts
- inventory counts can exist without a portable runtime object
- current tests preserve both models because both are still active

The project now needs containers, stacks, stack-based selection, and a clean migration path. Those requirements cannot be met cleanly by extending the current split model.

## 3. Design Goals

- Single runtime authority for all portable, movable, carriable, droppable, and container-stored items.
- Unified model for ordinary items and portable scene objects.
- Stack support as a core runtime concept.
- Derived actor inventory view from runtime item stacks.
- Eventual `selected_stack_id` selection path instead of plain `item_id`.
- Parent chain support for `actor`, `area`, and `item`.
- Containers without deeply nested stored JSON trees.
- Minimal helper layer for location/transfer logic.
- Clean phased migration with limited compatibility debt.
- No unnecessary new storage registry or heavy abstraction layer.

## 4. Non-Goals and Deferred Scope

The first v2 implementation does not define or expand the following systems:

- equipment / slots
- durability
- generalized weight system
- economy / value
- crafting
- advanced visibility / hidden-information rules
- ownership / legal / theft systems
- arbitrary deep engine-level semantics for `use`

Clarifications against current repo behavior:

- The repo already has a lightweight carry-mass rule in `scene_action take` / `detach` using entity `props.mass` and actor `meta.carry_mass_limit`.
- Item System v2 does not expand that into a general weight architecture in the first implementation.
- Existing carry-limit behavior can remain as legacy logic until item operations migrate in Phase 4.

## 5. Core Data Model

### 5.1 Authoritative storage target

Target authoritative storage:

```json
{
  "items": {
    "stk_torch_a1b2c3": {
      "stack_id": "stk_torch_a1b2c3",
      "definition_id": "torch",
      "label": "torch",
      "quantity": 2,
      "stackable": true,
      "parent_type": "actor",
      "parent_id": "pc_001",
      "is_container": false,
      "description": "a simple handheld torch for lighting dark areas",
      "tags": ["light_source"],
      "verbs": ["inspect", "drop"],
      "state": {},
      "props": {}
    },
    "stk_old_crate_d4e5f6": {
      "stack_id": "stk_old_crate_d4e5f6",
      "definition_id": "old_crate",
      "label": "Old Crate",
      "quantity": 1,
      "stackable": false,
      "parent_type": "area",
      "parent_id": "area_001",
      "is_container": true,
      "tags": ["container", "wood"],
      "verbs": ["inspect", "open", "search", "take"],
      "state": { "opened": false },
      "props": { "mass": 12, "size": "medium" }
    }
  }
}
```

`campaign.items` is the final runtime authority for portable items.

### 5.2 `RuntimeItemStack` schema

Required fields:

- `stack_id: str`
- `definition_id: str`
- `label: str`
- `quantity: int`
- `stackable: bool`
- `parent_type: "actor" | "area" | "item"`
- `parent_id: str`
- `is_container: bool`

Optional fields:

- `description: str`
- `tags: list[str]`
- `verbs: list[str]`
- `state: dict[str, object]`
- `props: dict[str, object]`

Normalization defaults for merge comparison and persistence:

- `description = ""`
- `tags = []`
- `verbs = []`
- `state = {}`
- `props = {}`

### 5.3 `definition_id` vs `stack_id`

`definition_id`:

- identifies the logical item definition
- is the aggregation key for compatibility inventory views
- is the lookup key for lightweight catalog metadata when available
- is not required to point to a rich external definition registry in v2 phase 1

`stack_id`:

- identifies a concrete runtime stack or instance
- is the unit of transfer, split, merge target selection, and future selection context
- format direction: `stk_<definition_id>_<short_unique_suffix>`

Repo-grounded adjustment:

- Because the repo does not currently have a comprehensive item-definition database, phase-1 migrations may use practical `definition_id` values that come from current inventory ids or migrated portable entity identifiers.
- `label`, optional `description`, `state`, `verbs`, and `props` therefore remain part of runtime stack storage instead of being assumed to exist elsewhere.

### 5.4 Parent semantics

First-version parent types:

- `actor`
- `area`
- `item`

Rules:

- `parent_type = "actor"` means the stack is directly carried by that actor.
- `parent_type = "area"` means the stack is directly placed in that area.
- `parent_type = "item"` means the stack is directly inside another stack that is a container.
- actor is not an item.
- area remains a direct storage parent type.

### 5.5 Container constraints

Containers are required in v2.

Rules:

- A stack can be a parent only when `is_container == true`.
- If `is_container == true`, `stackable` must be `false`.
- For first implementation, container items should be non-stackable in practice.
- A non-container stack must not have any child stacks.
- `parent_type = "item"` requires `parent_id` to reference an existing stack with `is_container == true`.

### 5.6 Cycle prevention

Item parent chains must never form cycles.

Required behavior:

- on any transfer to `parent_type = "item"`, walk the new parent chain before commit
- reject the operation if the target parent is the same stack or any descendant of the moving stack
- reject broken parent chains during validation

### 5.7 Stackability rules

Stackable stacks:

- may have `quantity > 1`
- may be split
- may merge when all merge preconditions pass

Non-stackable stacks:

- must have `quantity == 1`
- must not merge
- must not split into quantity fragments
- are still transferred by `stack_id`

Migration guidance:

- current count-only actor inventory entries such as `torch`, `tower_key`, or `required_item_001` should migrate as stackable unless repo behavior requires otherwise
- migrated portable scene objects and containers from `campaign.entities` should default to non-stackable

### 5.8 Merge rules

Two stacks may merge only when:

- both exist
- both are stackable
- both have the same `definition_id`
- both have the same `parent_type`
- both have the same `parent_id`
- both have the same normalized values for every stored field except:
  - `stack_id`
  - `quantity`

Merge result:

- target stack keeps its `stack_id`
- target `quantity += source.quantity`
- source stack is deleted

### 5.9 Split rules

Split preconditions:

- source exists
- source is stackable
- split quantity is a positive integer
- split quantity is strictly less than source quantity

Split result:

- source quantity is reduced
- new stack is created with:
  - new `stack_id`
  - same `definition_id`
  - same normalized non-quantity fields
  - same parent unless the split is immediately followed by transfer

### 5.10 Transfer rules

Transfer is the primitive runtime ownership/location change.

Rules:

- transfer keeps `stack_id`
- transfer changes only `parent_type` and `parent_id`
- if transfer quantity equals the full stack quantity, move the stack
- if transfer quantity is partial, split first and transfer the new stack
- after transfer, auto-merge into an eligible target stack if one exists in the destination parent

### 5.11 Delete-on-zero rule

If any operation reduces a stack quantity to zero:

- delete the stack from `campaign.items`
- treat any selected stack reference to that stack as stale
- backend validation must then ignore it on future turn requests

## 6. Parent / Location Resolution Layer

### 6.1 Purpose

Item System v2 needs a thin helper layer, not a new storage system.

Its job is to centralize the logic that is currently scattered across:

- `backend/app/tool_executor.py`
- `backend/app/scene_entities.py`
- `backend/api/routes/map.py`
- `backend/app/turn_service.py`

### 6.2 Required responsibilities

The helper layer must centralize:

- actor -> area resolution
- direct child listing for any parent
- root-parent resolution for stacks inside item parent chains
- area-visible item listing
- transfer between `actor` / `area` / `item`
- merge / split primitives
- cycle-prevention checks
- derived actor inventory aggregation

### 6.3 Recommended shape

Recommended implementation shape:

- one small module in `backend/app/`
- function-based or a small service object is sufficient
- no new storage registry
- all functions operate directly on `Campaign` and `campaign.items`

Recommended helper surface:

- `resolve_actor_area(campaign, actor_id) -> area_id | None`
- `list_item_children(campaign, parent_type, parent_id) -> list[RuntimeItemStack]`
- `resolve_stack_root_parent(campaign, stack_id) -> (parent_type, parent_id) | None`
- `list_area_visible_stacks(campaign, area_id, *, include_nested=False) -> list[RuntimeItemStack]`
- `derive_actor_inventory(campaign, actor_id) -> dict[definition_id, quantity]`
- `transfer_stack(...)`
- `split_stack(...)`
- `merge_stack_into(...)`
- `consume_stack(...)`

### 6.4 Visibility guidance

This helper owns area-level visibility policy so area coupling does not spread everywhere.

First-implementation guidance:

- keep the policy conservative
- direct area children are the minimum visible set
- nested container contents do not need automatic open-container UI exposure immediately
- the helper must still be capable of root resolution now, so later visibility work does not require another storage redesign

## 7. Inventory Derivation

### 7.1 Final authority

Final authority for carried items is `campaign.items`, not `actors[*].inventory`.

### 7.2 Derived actor inventory view

Derived actor inventory is an aggregated compatibility view:

- input: all stacks where `parent_type == "actor"` and `parent_id == actor_id`
- aggregation key: `definition_id`
- aggregated quantity:
  - sum stack quantities for stackable stacks
  - count non-stackable stacks as quantity `1` each

The derived view intentionally loses per-stack distinctions.

### 7.3 Transitional compatibility plan

During transition, keep `actors[*].inventory` only as a derived compatibility structure.

Rules:

- `actors[*].inventory` stops being authoritative as soon as `campaign.items` becomes active
- compatibility writes must be one-way from `campaign.items` into derived inventory
- gameplay code must not mutate `actors[*].inventory` directly once the cutover starts

### 7.4 API compatibility view

For short-term API/frontend compatibility, keep the legacy aggregated dict view temporarily:

- `campaign/get.actors[*].inventory`
- `state_summary.inventories`
- `state_summary.active_actor_inventory`

Those fields become compatibility outputs derived from `campaign.items`.

### 7.5 Eventual cleanup

After read-path migration and frontend stack adoption:

- remove `actors[*].inventory` from stored runtime authority
- then remove the compatibility mirror from `ActorState`

## 8. Selected Item Evolution

### 8.1 Current audited state

Current selected item is:

- frontend-owned
- per actor
- request-scoped
- keyed by plain `item_id`
- validated against aggregated actor inventory

Current wire path:

- request: `context_hints.selected_item_id`
- prompt context: `selected_item`
- trace debug: `debug.selected_item`

### 8.2 Target direction

Target selection identity is `stack_id`, not plain `item_id`.

Target request shape:

- `context_hints.selected_stack_id`

Target prompt context shape:

```json
{
  "selected_item": {
    "stack_id": "stk_torch_a1b2c3",
    "definition_id": "torch",
    "quantity": 2,
    "label": "torch"
  }
}
```

Optional metadata can still include:

- `description`
- `tags`

### 8.3 Validation rules

Backend remains authoritative.

Validation must ensure:

- stack exists
- stack is currently parented to the effective actor
- stack is still valid after any prior mutation

If invalid:

- do not fail the turn
- do not inject `selected_item` into prompt context
- do not inject selected-item debug info

This matches the already-confirmed stale-selection direction.

### 8.4 Transition strategy

Recommended transition:

1. Introduce backend support for `selected_stack_id`.
2. Temporarily accept both:
   - `selected_stack_id`
   - legacy `selected_item_id`
3. Prefer stack validation when both are present.
4. Migrate frontend store/UI from `selectedItemIdByActor` to stack-based state.
5. Remove `selected_item_id` after the frontend and tests stop using it.

### 8.5 Debug and summary implications

Recommended debug shape after stack migration:

```json
{
  "selected_item": {
    "stack_id": "stk_torch_a1b2c3",
    "definition_id": "torch",
    "has_metadata": true
  }
}
```

Selection should remain request-scoped, not part of authoritative campaign state.

Therefore:

- do not add selected item to stored campaign runtime state
- do not add selected item to state summary as authoritative state
- keep it as request/debug/prompt context only

## 9. Scene / World Interaction Mapping in v2

This section defines conceptual runtime ownership changes only. It does not prescribe immediate implementation refactors.

### 9.1 `take`

Conceptual v2 mapping:

- source stack currently visible/reachable in area or container
- transfer to `parent_type = "actor"`
- keep `stack_id`
- auto-merge if destination already has a compatible stack

### 9.2 `drop`

Conceptual v2 mapping:

- source stack currently parented to actor
- transfer to `parent_type = "area"` using actor's resolved area
- keep `stack_id`
- auto-merge if destination area already has a compatible stack

### 9.3 Move between containers

Conceptual v2 mapping:

- source stack transfer to `parent_type = "item"`
- target parent must be a container stack
- keep `stack_id`
- reject cycles
- auto-merge only when the destination container already has a compatible stack

### 9.4 `use` as context selection

Selected item itself has no engine-level meaning.

Rules:

- selecting an item or stack only changes prompt context
- selection alone does not mutate `campaign.items`
- future gameplay-specific `use` rules may consume, transfer, or mutate stacks explicitly, but that is not implicit engine behavior

### 9.5 `consume`

Conceptual v2 mapping:

- decrement stack quantity
- if quantity becomes zero, delete the stack
- if consuming part of a stack, keep the same `stack_id` for the remainder

### 9.6 `split`

Conceptual v2 mapping:

- create a second stack from part of a stackable source
- new stack gets a new `stack_id`

### 9.7 `merge`

Conceptual v2 mapping:

- merge only compatible stacks in the same parent
- keep target `stack_id`
- delete source stack

### 9.8 Spawn / create stack

Conceptual v2 mapping:

- create a new stack under `actor`, `area`, or `item`
- generate a new `stack_id`
- this replaces the need for item gains that exist only as aggregated count mutation

### 9.9 Remove stack

Conceptual v2 mapping:

- delete stack explicitly
- use only when quantity reaches zero or gameplay explicitly destroys/removes the item

## 10. Boundary With `campaign.entities`

This boundary is the key architectural rule.

### 10.1 What remains in `campaign.entities`

Keep fixed non-portable scene objects in `campaign.entities`, including:

- NPCs
- fixed doors / gates
- fixed clue sources
- fixed scenery
- other non-movable scene interactables

These remain scene entities because they are not portable runtime items.

### 10.2 What migrates into `campaign.items`

Move all portable runtime objects into `campaign.items`, including:

- inventory items currently stored only as aggregated counts
- portable world loot currently represented as entities
- carriable/droppable objects
- detachable objects after they become portable
- container items
- items stored inside container items

### 10.3 Portable scene-object rule

Portable scene-object runtime and ordinary item runtime become the same model.

Difference is parent/holder, not object kind.

### 10.4 Fixed entity rule

A fixed entity may still:

- reference item definitions for gameplay rules
- unlock or reveal items
- require an item for interaction

But it must not remain the authoritative storage location for portable item ownership once the refactor is complete.

### 10.5 Transition note for current entity-backed grants

Current fields such as:

- `inventory_item_id`
- `inventory_quantity`
- `inventory_granted`

remain acceptable as transitional compatibility on fixed entities during migration phases.

Final target:

- portable item authority lives in `campaign.items`
- fixed entities coordinate interactions but do not store portable item truth

## 11. Migration Strategy

### 11.1 Recommended migration style

Recommend a short transitional phase, not a long-lived dual-authority state.

Reason:

- old save compatibility is explicitly not required
- the repo already has broad test coverage that can be updated together
- prolonged dual authority would create drift between `actors[*].inventory`, `campaign.entities`, and `campaign.items`

### 11.2 Authority cutover recommendation

Recommended cutover:

- new campaigns and updated repo fixtures move to `campaign.items`
- `actors[*].inventory` becomes derived read-only compatibility data
- portable item logic gradually stops reading/writing old locations

### 11.3 `actors[*].inventory` during transition

Recommended policy:

- keep it derived and read-only
- write it only from compatibility derivation after item mutations
- remove it once frontend and API consumers no longer depend on it

### 11.4 Entity-backed item migration

Recommended treatment:

- portable entities in `campaign.entities` migrate into `campaign.items`
- fixed entities remain in `campaign.entities`
- entity-backed grant fields stay only until Phase 4 logic migration

### 11.5 Conversion helper / script

A repo-internal conversion helper is worthwhile.

Recommended scope:

- convert current preset/bootstrap/test fixture payloads into `campaign.items`
- derive compatibility `actors[*].inventory` during transition
- not intended as an end-user save migration system

Do not build a heavy multi-version save loader for old external saves.

### 11.6 Test fixture migration

Test fixtures should be migrated.

Recommendation:

- update fixture builders and world bootstrap helpers to emit `campaign.items`
- do not preserve old item fixtures longer than necessary
- keep only narrow compatibility tests for transitional API fields

## 12. Phased Implementation Roadmap

### Phase 0: Audit / Spec Freeze

Goal:

- freeze target model and migration plan before code work

Likely files / areas:

- `docs/01_specs/item_system_v2.md`

Changes:

- design only

Explicitly untouched:

- runtime code
- tests
- API
- frontend

Main risks:

- incomplete audit
- ambiguous migration sequencing

Completion criteria:

- one formal spec exists
- current split authority is mapped to real repo files
- target model and phase boundaries are explicit

### Phase 1: Introduce `campaign.items`

Goal:

- add the new runtime item schema and persistence surface

Likely files / areas:

- `backend/domain/models.py`
- `backend/infra/file_repo.py`
- `backend/app/turn_service.py`
- bootstrap sources:
  - `backend/app/world_presets.py`
  - `backend/app/scenario_runtime_mapper.py`
  - starter bootstrap in `backend/app/turn_service.py`

Changes:

- add `RuntimeItemStack`
- add `Campaign.items`
- add item validation / normalization
- bootstrap new campaigns with `campaign.items`
- derive compatibility inventories from item stacks

Explicitly untouched:

- `scene_action` behavior
- selected-item wire contract
- frontend inventory UI
- API response shapes

Main risks:

- temporary dual-write / dual-read drift
- unclear migration of current portable entities into initial stacks

Completion criteria:

- campaigns can persist `campaign.items`
- compatibility inventory views can be derived from it
- no new campaigns require `actors[*].inventory` as primary authority

### Phase 2: Move Read Paths to Unified Model

Goal:

- make read behavior use `campaign.items` instead of old inventory/entity authority

Likely files / areas:

- `backend/app/turn_service.py`
- `backend/api/routes/campaign.py`
- `backend/api/routes/map.py`
- `backend/app/scene_entities.py`
- new item helper module in `backend/app/`
- any move gate reads in `backend/app/tool_executor.py`

Changes:

- `derive_actor_inventory(...)` becomes the read source
- `campaign/get.actors[*].inventory` becomes derived output
- `state_summary.inventories` and `active_actor_inventory` become derived output
- move gating reads derived inventory, not `actor.inventory`
- area item listing starts using item helper logic

Explicitly untouched:

- stack-based selected item request contract
- scene-action mutation refactor
- frontend stack UI

Main risks:

- read-path drift between fixed entities and item stacks
- map/view and prompt scene regressions

Completion criteria:

- no authoritative read path depends on `actors[*].inventory`
- API compatibility outputs still match current frontend expectations

### Phase 3: `selected_item` -> stack reference

Goal:

- migrate request-scoped selected item from plain `item_id` to `stack_id`

Likely files / areas:

- `backend/api/routes/chat.py`
- `backend/app/turn_service.py`
- `frontend/store/store.js`
- `frontend/panels/actor_control_panel.js`
- selected-item tests

Changes:

- add `context_hints.selected_stack_id`
- validate against actor-owned stack presence
- inject stack-aware `selected_item` prompt context
- migrate frontend selection state to stack ids
- optionally accept legacy `selected_item_id` for one transition phase

Explicitly untouched:

- generic item operation semantics
- scene-action take/drop/container mutation logic

Main risks:

- UI stale-selection churn
- debug contract churn
- ambiguity if both item-id and stack-id hints are accepted temporarily

Completion criteria:

- valid stack selections inject context
- invalid selections are ignored authoritatively
- frontend can select a concrete stack, not just a definition id

### Phase 4: Migrate Runtime Take / Drop / Use / Container Behaviors

Goal:

- move runtime mutations onto item operations

Likely files / areas:

- `backend/app/tool_executor.py`
- new item operation helper module in `backend/app/`
- map/prompt area listing helpers
- preset/scenario item interaction tests

Changes:

- `take` delegates to stack transfer
- `drop` delegates to stack transfer
- `detach` spawns or converts to runtime item stack
- `search` fixed entities reveal/transfer stacks instead of only mutating aggregated counts
- `inventory_add` becomes a compatibility wrapper or delegates to item operations
- container movement uses `parent_type = "item"`

Explicitly untouched:

- equipment / durability / economy
- advanced visibility rules

Main risks:

- this is the hardest migration seam
- current entity-based clue-source and gate assumptions are embedded in scenario/preset flows
- carry-limit logic currently depends on entity-held portable items
- `scene_action use` currently mixes target mutation and `params.item_id` validation

Completion criteria:

- take/drop/search/detach no longer rely on split item authority
- portable item ownership changes are represented only in `campaign.items`

### Phase 5: Cleanup / Removal

Goal:

- remove transitional structures and old authority paths

Likely files / areas:

- `backend/domain/models.py`
- `backend/app/turn_service.py`
- `backend/api/routes/campaign.py`
- `backend/app/tool_executor.py`
- frontend store/UI compatibility logic
- obsolete tests and docs

Changes:

- remove stored `actors[*].inventory` authority
- remove portable items from `campaign.entities`
- remove legacy `selected_item_id` request path
- remove old entity-backed item grant authority
- prune compatibility tests and helpers

Explicitly untouched:

- future optional systems still out of scope

Main risks:

- cleanup debt if transition has already lingered too long
- hidden consumers of old fields

Completion criteria:

- one authoritative portable-item runtime remains: `campaign.items`
- `actors[*].inventory` is either gone or clearly a derived API-only artifact outside stored runtime state

## 13. `scene_action` Coupling Analysis

### 13.1 Current coupling to entity assumptions

Current `scene_action` implementation in `backend/app/tool_executor.py` is tightly coupled to `campaign.entities`.

Concrete couplings:

- target lookup is `campaign.entities[target_id]`
- reachability uses `EntityLocation`
- portability is inferred from entity `kind`
- container nesting is encoded as `loc.type == "entity"`
- `take` / `drop` / `detach` mutate entity `loc`
- `use` validates `params.item_id` by loading `campaign.entities[item_id]`
- `search` uses entity-state grant fields
- area search scans direct area entities for `inventory_item_id`
- carry mass is computed from actor-held portable entities

Prompt/tooling coupling also exists:

- `resources/prompts/turn_profile_default_v1.txt` still instructs the model to use `inventory_add` for inventory gain and `scene_action` for `take` / `drop` / `detach` / `use`
- `docs/01_specs/tools.md` describes the same current tool split

### 13.2 What should later move under the item operation layer

The following should move under the future item operation layer:

- stack transfer
- partial transfer via split
- merge on destination
- actor inventory derivation
- container parent validation
- cycle detection
- stack consumption
- mass calculation for portable items
- root-parent resolution for carried / contained stacks

Fixed scene interactions should stay outside that layer:

- NPC dialogue
- fixed door/gate logic
- non-portable scenery interaction

### 13.3 Dedicated item runtime operation layer recommendation

Recommendation: yes, a dedicated item runtime operation layer is warranted.

Reason:

- the current `scene_action` branch logic is already too coupled to low-level storage details
- containers and stacks will otherwise multiply special cases in `tool_executor.py`
- the required layer can still stay thin and pragmatic

Recommended role:

- one helper/service module in `backend/app/`
- storage-aware but not storage-owning
- invoked by `scene_action`, future item tools, and read-path helpers

### 13.4 Hardest migration points

Hardest points to migrate:

1. Entity-backed grant sources.
   - Current clue sources and searchable spots store grant authority in entity state.
2. `take` / `drop` split behavior.
   - Current portable entity movement is disconnected from actor inventory counts.
3. `use` mismatch.
   - Current request-selected item is prompt-only, but `scene_action use` checks `params.item_id` against entity-held items.
4. Carry-limit logic.
   - Current mass calculation scans actor-held entities, not aggregated inventory or runtime stacks.
5. Area display.
   - Current area display lists only direct area entities, not resolved item visibility roots.

## 14. API / Contract Forecast

### High-risk contracts

| Contract | Current shape | Likely v2 change |
| --- | --- | --- |
| `campaign/get.actors[*].inventory` | aggregated `{ item_id: quantity }` | remains temporarily as derived view, later may be supplemented or replaced by stack-aware payload |
| turn request `context_hints.selected_item_id` | plain item id | add `selected_stack_id`, deprecate plain id |
| frontend store `inventoryByActor` | aggregated by `item_id` | must eventually support stack-aware data |
| frontend selection state | `selectedItemIdByActor[item_id]` | migrate to stack ids |
| `scene_action use params.item_id` | plain entity id / item id | likely needs stack-aware or operation-layer semantics later |

### Medium-risk contracts

| Contract | Current shape | Likely v2 change |
| --- | --- | --- |
| `state_summary.inventories` | aggregated compatibility snapshot | can stay temporarily as derived view; may later gain stack-aware companion field |
| `state_summary.active_actor_inventory` | aggregated active actor snapshot | same as above |
| `debug.selected_item` | `{ id, has_metadata }` | likely becomes `{ stack_id, definition_id, has_metadata }` |
| prompt `selected_item` | `{ id, quantity, name?, description? }` | likely becomes stack-aware object with `stack_id` and `definition_id` |

### Low-risk contracts

| Contract | Current shape | Likely v2 change |
| --- | --- | --- |
| `campaign/get.status` | lifecycle snapshot | no item-driven change expected |
| world preview payload | world metadata | no direct item impact expected |

Recommendation:

- keep compatibility outputs stable until the frontend stack migration is ready
- do not remove aggregated views before stack-aware consumers exist

## 15. Test Impact Forecast

### Backend unit / integration

Needed test additions:

- stack validation
- stack id generation
- merge rules
- split rules
- transfer rules
- actor/area/item parent validation
- cycle prevention
- derived inventory aggregation
- stack-aware move gating
- item operation delegation from scene actions

Existing tests to update:

- `backend/tests/test_inventory_add_tool.py`
- `backend/tests/test_scene_action_tool.py`
- `backend/tests/test_scene_action_turn_api.py`
- `backend/tests/test_map_view_scene_entities.py`
- `backend/tests/test_turn_selected_item_context.py`
- `backend/tests/test_turn_response_contract_api.py`
- `backend/tests/test_watchtower_world.py`
- `backend/tests/test_watchtower_world_turn_api.py`
- `backend/tests/test_scenario_runtime_integration.py`
- `backend/tests/test_world_api.py`
- `backend/tests/test_move.py`
- `backend/tests/test_move_options.py`

### Frontend / store / UI

Needed test additions:

- stack-aware inventory store normalization
- per-actor selected stack state
- stale selected-stack clearing
- stack-aware inventory list rendering
- compatibility handling while aggregated API fields still exist

Existing tests to update:

- `frontend/tests/store_loop.test.mjs`
- `frontend/tests/inventory_items.test.mjs`

### API contract tests

Needed test additions:

- `campaign/get` compatibility inventory derivation from `campaign.items`
- turn request acceptance of `selected_stack_id`
- selected-item debug shape after stack migration
- map/view or equivalent area item listing when item read paths move

### Migration / conversion tests

Needed tests:

- preset/bootstrap conversion to `campaign.items`
- scenario runtime bootstrap conversion
- compatibility mirror derivation
- repo-internal conversion helper output validity

### Manual test flows

Recommended manual flows after migration phases:

- watchtower loop:
  - hint
  - one-time key acquisition
  - blocked fake inventory injection
  - gate unlock / goal completion
- scenario-backed world loop
- take/drop portable object loop
- container-to-actor and actor-to-container transfer
- stale selected stack after split / merge / consume

## 16. Risk Register

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Scope explosion | item runtime can easily expand into equipment, weight, economy, visibility, ownership | keep v2 first implementation limited to authority, stacks, containers, derived views, and selection migration |
| Stack merge mistakes | accidental merges can destroy instance-specific state | require identical normalized fields except `quantity` and `stack_id` |
| Selected-item contract churn | current UI and backend both use plain `item_id` | dual-accept stack id and item id briefly, then remove item id quickly |
| Prompt/runtime drift | selected item in prompt may not match runtime ownership after mutation | backend validates selection every request; invalid selection injects nothing |
| Entity-to-item migration ambiguity | current repo mixes fixed entities and portable entities | enforce the portable-vs-fixed boundary in this spec and convert bootstraps explicitly |
| UI/store assumption breakage | frontend currently assumes `{ item_id: quantity }` everywhere | keep derived compatibility views until stack-aware frontend work lands |
| Cleanup debt | long transition would leave three partial item models | keep transition short and remove old paths in Phase 5 |
| Container recursion / cycle issues | item-parent chains can become invalid or non-terminating | centralize cycle checks in one helper layer |
| Carry-limit regression | current mass calculation uses entity-held portable items | migrate mass reads with item operations in Phase 4; do not expand weight scope first |
| Hidden display regressions | map/view and prompt scene currently show only direct area entities | centralize area visibility policy before expanding nested display |

## 17. Recommended Next Action

The next Codex turn should implement Phase 1 only:

- add `RuntimeItemStack` and `campaign.items`
- add validation / normalization in persistence
- populate `campaign.items` in bootstrap paths for new campaigns and fixtures
- derive compatibility inventory views from `campaign.items`

Explicitly do not refactor `scene_action` mutation behavior yet in that next turn.

That is the cleanest next step because it establishes the new authority model without mixing it with the hardest coupling breakpoints in the same change.
