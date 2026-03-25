# Formal Gameplay Model v0

## 1. Overview

Formal Gameplay Model v0 is a design-time and validation-time layer.

It represents two structural views:

- Path Graph
- Goal Dependency Graph

Its purpose is to:

- ensure baseline scenario solvability
- detect obvious deadlocks and broken structural dependencies
- map both generated scenarios and selected authored presets into one formal shape

Formal Gameplay Model v0 is not:

- runtime authority
- an action system
- an NPC system
- a combat system

It is read-only and observational.

## 2. Scope Definition

### Included

- Path Graph
- Goal Dependency Graph
- critical item dependencies
- solvability validation
- partial deadlock detection
- generator mapping
- minimal preset adapter
- dependency mode at schema level only

### Explicitly Not Included

- NPC state
- combat
- consequence system
- runtime authority
- action semantics
- clue-truth reasoning
- social/time systems
- generic preset extraction framework
- cycle detection

## 3. Core Model (v0)

### Node types

- `area`
- `gate`
- `clue_source`
- `item_dependency`
- `goal`

Important:

- `Goal(...)` is the only authoritative goal representation.
- `Node(type="goal")`, if present, is optional and non-authoritative.

### Goal types

- `enter_area`
- `interact_entity`

### Edge types

- `transition`
- `blocks_transition`
- `reveals`
- `requires`
- `depends_on`
- `satisfies`
- `located_in`

### dependency_groups

- `dependency_groups` is defined in the schema.
- It is not active in current validation logic.
- It is reserved for future use.

## 4. Generator Path (Current State)

The generator path currently has the most complete formal coverage.

Current implementation:

- maps generated scenario areas deterministically into `area` nodes
- maps the generated gate entity into a `gate` node
- maps the generated clue source into a `clue_source` node
- maps the required item into an `item_dependency` node
- maps the goal into `Goal(type="enter_area")`

Current constraints:

- no milestone support
- no complex inference
- no alternative-route dependency activation
- no runtime-authoritative behavior

The generator mapper is intentionally minimal and deterministic.

## 5. Preset Path (Current State)

### 5.1 Watchtower

Watchtower currently has full critical-path formal coverage for v0.

Included:

- area path
- watchtower gate
- tower key item dependency
- `old_hut_clue` as the critical clue source
- `Goal(type="enter_area")` targeting `watchtower_inside`

Excluded:

- NPC hint semantics
- non-critical entities
- flavor-only content

### 5.2 Midnight Archive

Midnight Archive is only partially modeled in v0.

Current implementation models one critical route only:

- the service route

Current implementation does not model full multi-path structure:

- official route is not represented in the formal graph
- alternative route combinations are not represented

Reason:

- `dependency_groups` exists only at schema level and is not yet active

Current preset-local overrides:

- a synthetic service-route gate id is used for the formal graph
- `Goal(type="interact_entity")` is anchored to `forged_file_shelf`

This is a narrow preset-local adaptation only. It is not a generalized action model.

## 6. Validator (v0)

Only these rules are implemented:

- `V1`: reachability
- `V2`: gate dependency satisfiable
- `V3`: critical item reachable
- `V5`: missing structure

Current validator behavior:

- checks whether a goal target is reachable from `start_area_id`
- checks whether a gate has a satisfiable required-item path
- checks whether a critical item has a reachable clue source
- checks for missing start area, missing goal target, and missing node references in edges

Not implemented:

- cycle detection
- advanced dependency reasoning

## 7. Integration Boundary (CRITICAL)

Formal Gameplay Model v0 is:

- read-only
- non-authoritative
- observational only

It must not:

- affect turn execution
- affect tool execution
- affect inventory state
- affect goal completion timing
- block runtime flow

Current attachment points:

- generator path: attached as `formal_validation` on `ScenarioRuntimeBridge`
- preset path: attached as `formal_validation` on `CampaignWorldPreset` during preset bootstrap preparation

These attachments exist for inspection and validation only.

## 8. Known Limitations

- Midnight Archive is not fully modeled.
- `blocks_transition` encoding is limited.
- `dependency_groups` is not active.
- cycle detection is not implemented.
- preset adapter is hand-authored and not generic.

## 9. Risk Notes

- semantic drift is possible if goal nodes are reused as authoritative goal state
- preset mapping currently mixes extraction with narrow interpretation
- preset structures are not fully uniform, especially for goal completion shapes

## 10. Future Optional Extensions

- dependency_groups activation for multi-path support
- fuller Midnight Archive modeling
- cycle detection
- generalized preset extraction
- improved blocked-transition encoding
