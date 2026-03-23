import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadDebugPanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/debug_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("buildSelectionDebugView exposes active stack selection, fallback state, and stack snapshots", async () => {
  const { buildSelectionDebugView } = await loadDebugPanelModule();

  const view = buildSelectionDebugView({
    campaign: {
      active_actor_id: "pc_001",
    },
    selectedStackIdByActor: {
      pc_001: "stk_torch_b",
    },
    selectionAuditByActor: {
      pc_001: {
        mode: "item_adapter",
        actor_id: "pc_001",
        selected_stack_id: "stk_torch_b",
        selected_item_id: "torch",
      },
    },
    submitSelectionAuditByActor: {
      pc_001: {
        mode: "stack_primary",
        actor_id: "pc_001",
        selected_stack_id: "stk_torch_b",
        selected_item_id: "torch",
      },
    },
    inventoryStacksByActor: {
      pc_001: [
        { stack_id: "stk_torch_a", item_id: "torch", quantity: 1 },
        { stack_id: "stk_torch_b", item_id: "torch", quantity: 2 },
      ],
    },
  });

  assert.deepEqual(view, {
    actor_id: "pc_001",
    selected_stack_id: "stk_torch_b",
    selected_item_id: "torch",
    selection_mode: "item_adapter",
    submit_mode: "stack_primary",
    fallback_active: false,
    selection_audit: {
      mode: "item_adapter",
      actor_id: "pc_001",
      selected_stack_id: "stk_torch_b",
      selected_item_id: "torch",
    },
    submit_selection_audit: {
      mode: "stack_primary",
      actor_id: "pc_001",
      selected_stack_id: "stk_torch_b",
      selected_item_id: "torch",
    },
    inventory_stacks: [
      { stack_id: "stk_torch_a", item_id: "torch", quantity: 1 },
      { stack_id: "stk_torch_b", item_id: "torch", quantity: 2 },
    ],
  });
});

test("buildSelectionDebugView falls back to state_summary stack snapshots when store stacks are unavailable", async () => {
  const { buildSelectionDebugView } = await loadDebugPanelModule();

  const view = buildSelectionDebugView({
    campaign: {
      active_actor_id: "pc_001",
    },
    selectedStackIdByActor: {
      pc_001: null,
    },
    selectionAuditByActor: {
      pc_001: {
        mode: "item_fallback",
        actor_id: "pc_001",
        selected_item_id: "torch",
      },
    },
    submitSelectionAuditByActor: {
      pc_001: {
        mode: "item_fallback",
        actor_id: "pc_001",
        selected_item_id: "torch",
      },
    },
    stateSummary: {
      active_actor_id: "pc_001",
      active_actor_inventory_stacks: [
        { stack_id: "stk_torch_a", item_id: "torch", quantity: 1 },
      ],
    },
  });

  assert.equal(view.fallback_active, true);
  assert.equal(view.selection_mode, "item_fallback");
  assert.equal(view.submit_mode, "item_fallback");
  assert.deepEqual(view.inventory_stacks, [
    { stack_id: "stk_torch_a", item_id: "torch", quantity: 1 },
  ]);
});
