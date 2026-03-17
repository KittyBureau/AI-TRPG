# Item System Refactor Closure Note

Last updated: 2026-03-17

Status: complete. This file is retained as an archived closure summary, not an active work tracker.

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

## 2. Intentionally Deferred To Later Phases

The following concerns were intentionally left out of the completed refactor and should be treated as later-phase work:

- public request/response protocol migration from `selected_item_id` to `selected_stack_id`
- frontend inventory UI redesign for first-class stack selection
- broader stack-aware frontend/debug surfaces beyond current compatibility fields
- richer item effect framework or deeper stack-to-stack interaction design
- broader API redesign beyond the compatibility layer already implemented

## 3. Current Closure Interpretation

This refactor should now be treated as closed for Playable v1 and current backend/runtime work.

Practical meaning:

- portable item authority is stack-based
- entity state may still gate or expose scene interactions, but it is no longer the runtime authority for portable items
- compatibility fields remain in place for the existing frontend and request protocol

## 4. Recommended Next Primary Track

Recommended next implementation focus:

- `P2-11A Context Builder Infrastructure`

This file should remain in the repo as historical context for the completed refactor, but it should not be used as an active execution board.
