# Item System Refactor Closure Note

Last updated: 2026-03-23

Status: archived. The refactor and its follow-on integration closure are complete. This file is retained as historical summary only; use `docs/90_playable/ITEM_REFACTOR_CLOSURE_TODO.md` for the final closure status.

## 1. Implemented Runtime Baseline

The Item System Refactor is now complete in the current repository baseline.

Implemented outcomes:

- `campaign.items` is the authoritative portable-item runtime store
- `RuntimeItemStack` persists canonical `parent_type` / `parent_id`, a serialized `location` mirror, and reserved `metadata`
- `actors[*].inventory` is synchronized as a read-only derived compatibility view
- inventory read paths use pure item helpers
- generic stack mutation primitives exist for split / move / merge support
- `scene_action take`, `drop`, `detach`, and item-side `use` are stack-authoritative
- legacy portable-entity `take` / `drop` paths convert to stacks and remove the original entity
- portable loot is no longer created as authority-carrying entities
- `/map/view` keeps its existing top-level shape and projects area-root ground-item stacks into `entities_in_area`
- prompt, runtime, and trace/debug all use the same internal selected-stack resolution model
- trace/debug exposes `debug.selected_item_resolution` while preserving `debug.selected_item` compatibility

## 2. Originally Deferred To Later Phases

The following concerns were intentionally left out of the initial runtime cutover and were later closed by the integration-closure line:

- request/response migration to stack-first selection (`selected_stack_id` primary, `selected_item_id` fallback-only)
- frontend stack-first inventory authority cutover
- stack-aware UI/debug alignment over the existing aggregated presentation
- compatibility cleanup to isolate remaining fallback and derived-only seams

Not closed as part of that line:

- first-class multi-stack picker UX
- broader item-effect framework expansion
- versioned API removal of stable compatibility outputs

## 3. Current Closure Interpretation

This refactor should now be treated as fully closed for Playable v1 and current backend/runtime/frontend work.

Practical meaning:

- portable item authority is stack-based
- entity state may still gate or expose scene interactions, but it is no longer the runtime authority for portable items
- stack-first is the normal backend/frontend/UI/debug model
- remaining compatibility is explicit, narrow, and secondary only

## 4. Recommended Next Primary Track

Recommended next implementation focus:

- `P2-11A Context Builder Infrastructure`

This file should remain in the repo as historical context for the completed refactor, but it should not be used as an active execution board.
