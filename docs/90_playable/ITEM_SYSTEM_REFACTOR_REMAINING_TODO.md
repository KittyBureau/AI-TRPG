# Item System Refactor Remaining TODO

Last updated: 2026-03-13

## 1. Current Refactor Status

The following phases are complete:

- Phase 1: portable item authority moved to `campaign.items`
- Phase 2: inventory read paths unified to pure item helpers
- Phase 3: `selected_stack_id` introduced as internal selection authority
- Phase 4A: stack-aware `scene_action take/drop`
- Phase 4B: stack-backed container `open/search`
- Phase 4C: `scene_action use` item-side migration to stack authority

These phases are complete and should be treated as baseline.

## 2. Remaining Refactor Work

Primary remaining migration:

- Phase 4D: detach migration

Goal:

- Convert entity detach operations into stack-authoritative item creation

Expected runtime behavior:

`entity target`
`-> validate detachable entity`
`-> create RuntimeItemStack`
`-> parent_type="actor"`
`-> remove entity from campaign.entities`

## 3. Planned Minimal Implementation Slice

Phase 4D-A

Scope:

- detach non-container entities
- reject entity containers
- reject entities with child entities
- create stack with `quantity=1`
- set `stackable=false`
- use `definition_id = entity.id`
- remove entity from `campaign.entities`
- new stack becomes authoritative inventory item

## 4. Risks Noted In Audit

- entity graph integrity
- entity containers
- child entities under detachable entities
- hybrid carry-mass logic
- rollback safety across `campaign.entities` and `campaign.items`
- prompt visibility assumptions while scene/map remain partly entity-centric

## 5. Likely Files Involved In Phase 4D Implementation

Implementation files:

- `backend/app/tool_executor.py`
- `backend/app/item_operations.py`
- `backend/app/item_runtime.py`
- `backend/app/turn_service.py`

Tests likely affected:

- `backend/tests/test_scene_action_tool.py`
- `backend/tests/test_scene_action_turn_api.py`
- `backend/tests/test_map_view_scene_entities.py`

## 6. Explicitly Out Of Scope For Now

Do not include the following in detach migration:

- stack-aware frontend redesign
- map/view stack visibility redesign
- stack-to-stack interaction
- item effect framework redesign
- broad API redesign

## 7. Recommended Next Step When Development Resumes

Implement **Phase 4D-A** only.

Keep the implementation small and rollback-safe.

Do not attempt full detach migration in one step.
