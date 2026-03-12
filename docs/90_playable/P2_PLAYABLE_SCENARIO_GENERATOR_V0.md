# Playable Scenario Generator v0

Last updated: 2026-03-12

## 1. Alignment summary

- Current stable source example: `test_watchtower_world`.
- Current verified loop: spawn -> talk guard -> search hut clue -> obtain key -> enter gate -> `goal_achieved`.
- Scope of this design: extract the watchtower loop into one reusable playable scenario template and define the smallest generator shape that can reproduce a structurally equivalent scenario.
- Non-goals for this round:
  - full world generation
  - free-form narrative generation
  - multi-template architecture
  - runtime-system redesign
- v0 target: generate one small, solvable, immediately playable scenario that stays compatible with the existing world model, campaign bootstrap, map movement, `scene_action`, inventory authority, move gate logic, and goal completion flow.

## 2. Watchtower structure extraction

Source-of-truth files used for extraction:

- `backend/app/world_presets.py`
- `backend/app/turn_service.py`
- `backend/app/tool_executor.py`
- `backend/tests/test_watchtower_world.py`
- `backend/tests/test_watchtower_world_turn_api.py`

Observed watchtower structure:

- Area count: 6
- Layout type: branched hub plus gated tail
- Objective flow: find one required item before entering one gated target area

Structural roles separated from flavor:

- Start area role
  - Current watchtower value: `village_gate`
  - Function: actor spawn area and first decision point
- Hint source role
  - Current watchtower value: `npc_village_guard`
  - Function: exposes the clue path via `scene_action: talk`
- Clue area role
  - Current watchtower value: `old_hut`
  - Function: reachable pre-gate area that contains the item source
- Clue source role
  - Current watchtower value: `old_hut_clue`
  - Function: searchable entity that grants the required item once
  - Current runtime also supports area-level search on `old_hut` because `scene_action search` can resolve an area inventory source
- Granted item role
  - Current watchtower value: `tower_key`
  - Function: required inventory item for gated movement
- Gate area role
  - Current watchtower value: `watchtower_entrance`
  - Function: area immediately before the locked transition
- Gate entity role
  - Current watchtower value: `watchtower_door`
  - Function: scene-facing locked object for flavor and inspection
- Required item role
  - Current watchtower value: `tower_key`
  - Function: item checked by `required_item_for_move(world_id, from_area_id, to_area_id)`
- Target area role
  - Current watchtower value: `watchtower_inside`
  - Function: destination behind the gate
- Objective type
  - Current watchtower value: enter the target area after obtaining the key
- Success condition type
  - Current watchtower value: move into target area -> `campaign.goal.status = "completed"` -> lifecycle ends as `goal_achieved`

Reusable structural pattern:

- start area
- optional start-area hint source
- reachable exploration hub / transit area
- reachable clue area
- one searchable clue source that grants one required item once
- gate area on the route to the target
- one locked move edge that checks the required item
- one target area behind that gate
- one enter-target success rule

## 3. Proposed `key_gate_scenario` template definition

Template id:

- `key_gate_scenario`

Fixed structural logic:

- exactly 1 start area
- exactly 1 clue area
- exactly 1 clue source
- exactly 1 granted key item
- exactly 1 gated move rule
- exactly 1 target area
- exactly 1 objective: enter target area
- exactly 1 success rule: entering target area completes the campaign goal
- default v0 includes exactly 1 hint source placed in the start area or first hub area

Parameterizable content:

- theme
- world name
- area_count
- layout_type
- difficulty
- item label
- gate label
- hint source label
- clue source label
- area names and descriptions
- objective wording

Minimal internal template output shape:

```json
{
  "template_id": "key_gate_scenario",
  "template_version": "v0",
  "world": {
    "world_id": "generated_world_id",
    "name": "Generated World",
    "seed": 123,
    "world_description": "Short scenario summary",
    "objective": "Find the key and enter the target area.",
    "start_area": "area_start",
    "generator": {
      "id": "playable_scenario_v0",
      "version": "1",
      "params": {}
    }
  },
  "bootstrap": {
    "start_area_id": "area_start",
    "goal_text": "Find the key and enter the target area.",
    "map_data": {},
    "entities": {}
  },
  "rules": {
    "move_gates": [
      {
        "from_area_id": "area_gate",
        "to_area_id": "area_target",
        "required_item_id": "item_key",
        "gate_entity_id": "gate_001"
      }
    ],
    "goal": {
      "type": "enter_area",
      "target_area_id": "area_target"
    }
  }
}
```

Why this shape is repo-aligned:

- `world` matches the existing `World` resource contract
- `bootstrap` matches the existing `_build_campaign_bootstrap()` payload shape
- `rules` matches the two current runtime hooks already used by `tool_executor.py`: gated move checks and goal-area completion

## 4. Proposed parameter model

Minimal external input model:

- `scenario_template`
  - required
  - fixed to `key_gate_scenario` in v0
- `theme`
  - required
  - short content direction such as `watchtower`, `crypt`, `ruins`, `outpost`
- `area_count`
  - optional
  - integer `4..8`
  - default `6`
- `layout_type`
  - optional
  - `linear` or `branched`
  - default `branched`
- `difficulty`
  - optional
  - `easy` or `standard`
  - default `easy`

Optional content override bucket:

- `labels`
  - `item`
  - `gate`
  - `hint_source`
  - `clue_source`
  - `target_area`
- `descriptions`
  - per-area and per-entity short text overrides
- `objective_text`
  - override only if caller needs explicit wording

Minimal behavior of parameters in v0:

- `theme` controls names and text flavor
- `area_count` controls how many neutral transit areas are inserted around the fixed role skeleton
- `layout_type` controls whether clue and gate branches split off a hub or sit on one linear route
- `difficulty` changes distance and placement only
  - not lock count
  - not item count
  - not success-rule complexity

Recommended normalized internal params persisted in `World.generator.params`:

```json
{
  "mode": "playable_scenario",
  "template_id": "key_gate_scenario",
  "template_version": "v0",
  "theme": "watchtower",
  "area_count": 6,
  "layout_type": "branched",
  "difficulty": "easy"
}
```

## 5. Proposed generation pipeline

Conceptual flow:

- parameters
- choose template
- normalize params
- generate topology skeleton
- assign structural roles
- generate area/entity content
- place clue source and granted item
- place gated move rule and target area
- define objective and success rule
- validate solvability
- produce world/bootstrap/rules payload

Minimal v0 pipeline in repo terms:

1. Accept `scenario_template`, `theme`, `area_count`, `layout_type`, `difficulty`.
2. Normalize and bound values.
3. Pick one deterministic topology skeleton for `linear` or `branched`.
4. Assign role areas:
   - `start_area_id`
   - optional `hub_area_id`
   - `clue_area_id`
   - `gate_area_id`
   - `target_area_id`
5. Fill any remaining areas as neutral transit areas.
6. Create entities:
   - one hint source NPC or object
   - one clue source entity with `inventory_item_id`, `inventory_quantity = 1`, `inventory_granted = False`
   - one gate entity with `locked = True` and `required_item_id`
7. Create move gate rule for `gate_area_id -> target_area_id`.
8. Set goal rule to `enter_area(target_area_id)`.
9. Run validation rules.
10. Return the scenario instance payload.

Watchtower-equivalent v0 instance shape:

- start at a public approach area
- optionally talk to one hint source
- move into one clue area
- search one clue source to get one key
- walk to one gate entrance
- move through one locked transition into one target area
- objective completes immediately on entry

## 6. Proposed solvability validation rules

Mandatory validation rules:

- `start_area_id` exists in `map_data.areas`
- `target_area_id` exists in `map_data.areas`
- clue area exists and is distinct from target area
- gate area exists and is distinct from target area
- clue source entity exists in the clue area
- clue source supports `search`
- clue source declares:
  - `inventory_item_id`
  - `inventory_quantity > 0`
  - `inventory_granted = False`
- gate entity exists in the gate area
- gate entity declares `required_item_id`
- move gate rule exists for `gate_area_id -> target_area_id`
- clue source granted item id exactly matches the gate required item id
- a path exists from start area to clue area without crossing the gated edge
- a path exists from start area to gate area without needing the gated edge
- a path exists from gate area to target area through the gated edge
- after granting the required item, a path exists from start area to target area
- no ungated alternate path exists from start area to target area that bypasses the required gated edge
- goal rule target area exactly matches the gated destination target area
- success condition is satisfiable by the existing runtime:
  - actor can legally `move` into `target_area_id`
  - goal completion is triggered by entering that area

Recommended validation rules:

- start area has at least one reachable neighbor
- hint source, when present, is reachable from the start area without movement or within the first hop
- all areas belong to one connected component
- all reachable links are bidirectional for v0 unless a template explicitly declares otherwise
- role ids are stable and deterministic under the same normalized params and seed

## 7. Minimal integration plan

Goal: fit the generator into the current architecture with the fewest new seams.

Recommended new code locations:

- `backend/domain/scenario_models.py`
  - minimal internal scenario data shapes
- `backend/app/scenario_templates.py`
  - fixed template definitions and watchtower-template extraction helpers
- `backend/app/scenario_generator.py`
  - topology assignment, content fill, and validation

Recommended existing integration points:

- `backend/app/world_presets.py`
  - keep as the built-in world entrypoint
  - refactor watchtower preset to be representable as `key_gate_scenario` Template 0 data
- `backend/app/world_service.py`
  - later add a minimal scenario-world generation path that writes a normal `World` resource whose `generator.params` store normalized scenario params
- `backend/app/turn_service.py`
  - later make campaign bootstrap world-resource-aware so a generated world can rebuild its scenario bootstrap from stored generator params plus seed
- `backend/app/tool_executor.py`
  - later resolve gated move rules and goal-area completion from a scenario definition lookup instead of only hard-coded watchtower functions

Recommended output contract for runtime use:

- `World`
  - existing metadata object, persisted as today
- `bootstrap`
  - `start_area_id`
  - `goal_text`
  - `map_data`
  - `entities`
- `rules`
  - `move_gates`
  - `goal`

Recommended entry path into the current world/campaign pipeline:

1. World source remains either built-in preset or stored `World` resource.
2. For generated scenarios, persist only the `World` metadata plus normalized scenario params in `World.generator.params`.
3. At campaign creation time, load that `World` resource and deterministically rebuild the scenario `bootstrap` and `rules`.
4. Feed `bootstrap` directly into the existing campaign creation path.
5. Keep `tool_executor.py` move and goal checks unchanged at the call site by swapping only the lookup backend used by:
   - `required_item_for_move(...)`
   - `is_goal_area(...)`

Why this is the smallest viable integration:

- no new campaign runtime system
- no new frontend requirement
- no parallel scenario execution path
- no need to persist a second world-sized content file for v0 if generation is deterministic from `world_id`, seed, and normalized params

## 8. Exact file list to create or update for the design/TODO phase

Create:

- `docs/90_playable/P2_PLAYABLE_SCENARIO_GENERATOR_V0.md`

Update:

- `docs/90_playable/PLAYABLE_V1_TODO.md`
- `docs/00_overview/PROJECT_STATUS.md`
- `docs/01_specs/TODO_DOCS_ALIGNMENT.md`
- `docs/20_runtime/testing/test_watchtower_world_manual_test.md`

No runtime code change is required in this design-only round.

## 9. Important design decisions requiring confirmation before implementation

- Storage strategy for generated scenarios
  - Recommended: persist only `World` metadata plus normalized generator params, then rebuild the scenario deterministically at campaign creation time.
  - Reason: this fits the current `storage/worlds/<world_id>/world.json` contract and avoids a new scenario storage layer in v0.
- Hint source policy
  - Recommended: keep exactly one hint source in every `key_gate_scenario` v0 instance, with watchtower remaining the reference behavior.
  - Reason: the watchtower baseline already proves the talk -> clue -> key -> gate loop and the extra hint source is cheap to support.
- Difficulty scope
  - Recommended: difficulty changes placement and wording only, not lock count or rule complexity.
  - Reason: v0 should optimize for guaranteed solvability and structural equivalence to the watchtower smoke path, not content richness.
