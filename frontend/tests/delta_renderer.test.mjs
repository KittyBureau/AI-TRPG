import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadDeltaRendererModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/renderers/delta_renderer.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("buildDelta tracks stack-level inventory changes alongside aggregated inventory changes", async () => {
  const { buildDelta, renderDeltaLines } = await loadDeltaRendererModule();

  const delta = buildDelta(
    {
      active_actor_id: "pc_001",
      inventories: {
        pc_001: { torch: 1 },
      },
      inventory_stacks: {
        pc_001: [
          { stack_id: "stk_torch_a", item_id: "torch", quantity: 1 },
        ],
      },
    },
    {
      active_actor_id: "pc_001",
      inventories: {
        pc_001: { torch: 2 },
      },
      inventory_stacks: {
        pc_001: [
          { stack_id: "stk_torch_a", item_id: "torch", quantity: 1 },
          { stack_id: "stk_torch_b", item_id: "torch", quantity: 1 },
        ],
      },
    },
    "pc_001"
  );

  assert.equal(delta.inventory.changed, true);
  assert.deepEqual(delta.inventory.stack_changes, [
    {
      stack_id: "stk_torch_b",
      item_id: "torch",
      before_quantity: 0,
      after_quantity: 1,
      delta: 1,
    },
  ]);
  assert.deepEqual(renderDeltaLines(delta), [
    "inventory: torch (+1)",
    "inventory_stack: stk_torch_b torch (+1)",
  ]);
});
