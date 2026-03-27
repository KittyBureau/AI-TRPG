# Formal Gameplay Model

## 1. Overview

Formal Gameplay Model is a design-time and validation-time layer.

It represents two structural views:

- Path Graph
- Goal Dependency Graph

Its current implemented purpose is to:

- ensure baseline scenario solvability
- detect broken structural dependencies
- expose quality, authoring-audit, preset-alignment, and remediation-planning views on top of the same formal output

Formal Gameplay Model is not:

- runtime authority
- an action system
- an NPC system
- a combat system

It is read-only, observational, and non-authoritative.

## 2. Scope Definition

### Included

- Path Graph
- Goal Dependency Graph
- critical item dependencies
- solvability validation
- dependency groups with `all_of` / `any_of`
- multi-path coverage validation
- clue-support coverage validation
- quality aggregation
- authoring audit output
- generator mapping
- minimal preset adapter
- preset alignment audit
- remediation backlog summary

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
- runtime optimization or auto-remediation

## 3. Core Model (Current)

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
- Current supported modes are:
  - `all_of`
  - `any_of`
- Each gate currently binds at most one dependency group.

### Annotation and audit outputs

- generator-side shaping annotations:
  - `gate_clue`
  - `gate_clue_support_gap`
- validation-time audit outputs:
  - `gate_quality_statuses`
  - `overall_quality_status`
  - gate-level authoring audit
  - overall authoring audit
  - preset alignment audit
  - preset alignment backlog summary

## 4. Validator (Current State)

Current formal validation includes:

- `V1`: reachability
- `V2`: gate dependency satisfiable
- `V3`: critical item reachable
- `V5`: missing structure
- `multi_path_coverage` for `any_of` gates
- `clue_support_coverage` for `any_of` candidate paths
- gate-level quality aggregation
- overall quality aggregation
- gate-level authoring audit
- overall authoring audit

Not implemented:

- cycle detection
- route scoring
- runtime feedback or auto-repair

These checks do not change `main_path_solvable` semantics beyond their existing structural role, and they do not affect runtime execution.

## 5. Generator Path (Current State)

The generator path currently has the most complete formal coverage.

Current implementation:

- maps generated scenario areas deterministically into `area` nodes
- maps generated gates into `gate` nodes
- maps clue sources into `clue_source` nodes
- maps required items into `item_dependency` nodes
- maps goals into `Goal(...)`
- emits shaping annotations where clue support can be inferred:
  - `gate_clue`
  - `gate_clue_support_gap`

The generator mapper is minimal and deterministic. It does not rewrite dependency semantics and does not consume validator results as feedback.

## 6. Preset Path (Current State)

### 6.1 Watchtower

Watchtower currently remains the legacy baseline.

Current formal expression includes:

- critical-path area traversal
- gate and required item mapping
- solvability validation

Current formal expression does not yet include:

- explicit `dependency_group`
- stable `gate_clue` annotation
- modern preset-alignment signals beyond the legacy baseline

### 6.2 Midnight Archive

Midnight Archive is the current partial preset alignment sample.

Current implementation models one critical formal route only:

- the service route

Current formal expression includes:

- explicit service-route gate formalization
- explicit `dependency_group`
- explicit `gate_clue`
- `Goal(type="interact_entity")` anchored to `forged_file_shelf`
- stable quality and authoring-audit output

Current implementation does not model full alternative-route coverage for the preset.

Because current formal coverage is intentionally limited to the service route, `midnight_archive_world` is currently expected to remain `partial`, not `aligned`.

## 7. Alignment Audit and Backlog Output

Current preset-alignment audit output includes:

- `alignment_level`
  - `legacy`
  - `partial`
  - `aligned`
- `priority_hint`
  - `high`
  - `medium`
  - `low`

Current remediation backlog output includes:

- `gap_type`
  - `missing_dependency_group_alignment`
  - `missing_gate_clue_alignment`
  - `missing_authoring_audit_visibility`
  - `shaping_gap_unexposed`
  - `limited_preset_coverage_alignment`
- `recommended_target`
  - `adapter_only`
  - `formal_annotation`
  - `future_optional`
- structured backlog summary counts and per-preset plans

Current audit semantics are intentionally conservative:

- `aligned` means the preset is stably connected to the modern formal/audit output shape and also has full mapped preset-area coverage for the current adapter scope.
- `partial` includes route-limited or sample-only preset mappings that already expose modern formal/audit signals but do not yet cover the full preset structure.

These outputs are planning and review views only. They do not change formal validity or runtime behavior.

## 8. Integration Boundary (CRITICAL)

Formal Gameplay Model is:

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

Related current gameplay validation boundary:

- generation-time static path and clue validation now run in the scenario builder/validator chain, but they are not part of the formal model
- runtime hostility and `progression_locked` outcomes also live outside the formal model
- none of these runtime-facing systems make the formal layer authoritative

## 9. Known Limitations

- Midnight Archive is not fully modeled.
- `blocks_transition` encoding is limited.
- cycle detection is not implemented.
- preset adapter is hand-authored and not generic.
- preset alignment audit and backlog outputs currently cover only presets that already have a formal preset mapper path.

## 10. Risk Notes

- semantic drift is possible if goal nodes are reused as authoritative goal state
- preset mapping currently mixes extraction with narrow interpretation
- preset structures are not fully uniform, especially for goal completion shapes
- shaping gaps remain formal annotations only and must not be mistaken for runtime clue sources

## 11. Boundary Reminder

- All current formal outputs are read-only and non-authoritative.
- None of the formal validator, audit, alignment, or backlog layers affect runtime authority.
- None of these layers affect turn execution or tool execution.
