# ITEM REFACTOR - INTEGRATION CLOSURE TODO

## 0. Status

Closure complete as of 2026-03-23.

The item-system refactor is now closed with stack-first authority across backend runtime, frontend store, selection/submit flow, and UI/debug surfaces. Remaining compatibility is narrow and explicit only.

## 1. Final Phase Status

1. Stack-First Inventory Contract
Goal: expose stack-first inventory payloads as the primary frontend contract.
Status: completed.

2. Frontend Store Authority Cutover
Goal: make frontend inventory authority derive from stack-first payloads.
Status: completed.

3. Selection / Submit Cutover
Goal: make `selectedStackId` / `selected_stack_id` the primary selection and submit path.
Status: completed.

4. UI / Debug Alignment
Goal: make visible inventory, selection, and debug surfaces reflect the stack-first model.
Status: completed.

5. Compatibility Cleanup
Goal: remove or isolate temporary compatibility paths after stack-first closure was stable.
Status: completed with narrow intentional residual compatibility.

---

## 2. Completion Record by Phase

## Phase 1: Stack-First Inventory Contract

### Goal
Campaign load and post-turn responses expose stack-first inventory payloads sufficient for frontend authority.

### Tasks

- [x] Define stack-first campaign load inventory contract
description: `GET /api/v1/campaign/get` exposes `inventory_stacks` as the primary inventory contract.
scope: campaign load response, serializer surfaces.
depends_on: none
done_when: frontend can hydrate inventory authority from stack payloads without needing aggregated inventory as primary input.

- [x] Define stack-first post-turn inventory contract
description: turn `state_summary` exposes `inventory_stacks` and `active_actor_inventory_stacks`.
scope: chat turn response, `state_summary`.
depends_on: none
done_when: post-turn reconciliation can use stack payloads as primary authority.

- [x] Mark compatibility inventory outputs explicitly
description: aggregated inventory outputs remain available only as derived compatibility snapshots.
scope: campaign load responses, turn/state responses, code comments, docs.
depends_on: Phase 1 task 1, Phase 1 task 2
done_when: stack payloads are documented as primary and aggregate payloads are documented as compatibility-only.

## Phase 2: Frontend Store Authority Cutover

### Goal
Frontend inventory authority is stack-first and aggregated inventory is derived display state only.

### Tasks

- [x] Replace item-first inventory authority in the frontend store
description: store inventory authority derives from `inventory_stacks`.
scope: play store state model, hydration state, reconciliation state.
depends_on: Phase 1
done_when: aggregated inventory is no longer a primary authority input.

- [x] Unify campaign-load and post-turn hydration on the same stack-first source
description: campaign refresh and turn-result ingestion both prefer stack payloads.
scope: campaign hydration path, post-turn ingestion path.
depends_on: Phase 1
done_when: load and post-turn flows use the same stack-first authority model.

- [x] Keep aggregated display derivation separate from authority
description: grouped item display remains allowed as a derived presentation view only.
scope: derived views, inventory presentation inputs.
depends_on: Phase 2 task 1, Phase 2 task 2
done_when: removing aggregate payloads as authority would not break frontend correctness.

## Phase 3: Selection / Submit Cutover

### Goal
`selectedStackId` is the frontend selection authority and `selected_stack_id` is the normal submit field.

### Tasks

- [x] Make stack id the only primary selection authority
description: selection is stored and reconciled by stack identity.
scope: frontend selection state, restore logic, reconciliation logic.
depends_on: Phase 2
done_when: normal selection behavior no longer requires item id as authority.

- [x] Make turn submit stack-first
description: normal requests submit `selected_stack_id`.
scope: turn submit flow, request construction.
depends_on: Phase 2
done_when: `selected_item_id` is no longer emitted as a co-equal path.

- [x] Make compatibility fallback observable
description: any remaining item-id fallback is explicitly auditable.
scope: submit flow, debug surfaces, selection audit state.
depends_on: Phase 3 task 1, Phase 3 task 2
done_when: fallback use is distinguishable from normal stack-first behavior.

## Phase 4: UI / Debug Alignment

### Goal
User-visible inventory and debug surfaces reflect the same stack-first selection/inventory model used internally.

### Tasks

- [x] Align inventory and selected-item UI to stack-first authority
description: inventory rows are derived from stacks and selection highlight follows selected stack.
scope: actor control panel, inventory rendering helpers.
depends_on: Phase 3
done_when: visible selection matches stack authority rather than item-only state.

- [x] Align debug and trace surfaces to selection resolution
description: debug UI shows stack selection, submit mode, fallback state, and stack snapshots.
scope: debug panel, raw response/debug surfaces.
depends_on: Phase 3
done_when: selection resolution and fallback state are visible without manual inference.

- [x] Align secondary item-related displays
description: secondary inventory displays no longer imply aggregate inventory is authoritative.
scope: delta/summary views, raw console item snapshots.
depends_on: Phase 2
done_when: stack-first authority is clear across visible item-related surfaces.

## Phase 5: Compatibility Cleanup

### Goal
Remove unnecessary bridges and isolate the small amount of compatibility that still remains justified.

### Tasks

- [x] Retire compatibility inventory dependency
description: remove compatibility aggregated inventory from any primary frontend integration role.
scope: frontend store authority, UI/rendering authority, reconciliation logic.
depends_on: Phases 1-4
done_when: aggregated inventory remains derived-only and is not used as authority input.

- [x] Retire `selected_item_id` primary usage
description: remove item-id selection from any normal primary integration role.
scope: frontend selection state, normal submit path, UI/debug semantics.
depends_on: Phases 1-4
done_when: `selected_item_id` remains only as explicit fallback compatibility.

- [x] Close compatibility cleanup as a separate validation phase
description: record what compatibility remains and why.
scope: closure validation, status landing, residual compatibility report.
depends_on: Phase 5 task 1, Phase 5 task 2
done_when: residual compatibility is documented explicitly and no longer ambiguous.

---

## 3. Final Cross-Phase Decisions

- backend, frontend store, selection/submit, and UI/debug are documented as stack-first
- aggregated inventory is display/debug compatibility only
- selected item authority is `selectedStackId`
- `selected_stack_id` is the normal submit path
- `selected_item_id` is fallback-only compatibility
- fallback must remain explicit and observable
- do not reopen feature scope from this closure doc

---

## 4. Residual Compatibility

- Backend request support for `context_hints.selected_item_id`
reason: fallback-only compatibility for callers that cannot yet resolve a stack id.
type: fallback-only
future: removable only after API-level migration evidence

- Backend aggregate inventory outputs (`actors[*].inventory`, `state_summary.inventories`, `active_actor_inventory`, companion `*_stack_ids`)
reason: stable compatibility snapshots for existing consumers and tests.
type: derived-only
future: acceptable to retain unless a versioned contract cleanup is required later

- Frontend aggregate inventory views (`inventoryByActor`, `inventoryStackIdsByActor`)
reason: current UI still renders grouped item rows.
type: derived-only
future: acceptable permanent compatibility if they remain explicitly derived

- Frontend item-click selection adapter (`setSelectedItemForActor(...)`)
reason: current UI remains visually aggregated.
type: adapter-only
future: removable only if a dedicated stack-picker UX replaces item-level selection

---

## 5. Closure Result

- Main item refactor closure line is complete.
- The repo now behaves stack-first end-to-end for the primary path.
- Remaining compatibility is explicit, narrow, and non-authoritative.
- Future work should treat this line as closed unless a deliberate versioned compatibility cleanup is planned.

