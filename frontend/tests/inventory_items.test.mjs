import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadInventoryItemsModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/utils/inventory_items.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("buildInventoryItemViews maps known catalog metadata and selected state", async () => {
  const { buildInventoryItemViews } = await loadInventoryItemsModule();

  const views = buildInventoryItemViews(
    {
      tower_key: 1,
      torch: 2,
    },
    "torch"
  );

  assert.deepEqual(views, [
    {
      item_id: "torch",
      name: "torch",
      description: "a simple handheld torch for lighting dark areas",
      quantity: 2,
      is_selected: true,
    },
    {
      item_id: "tower_key",
      name: "tower key",
      description: "the iron key that unlocks the abandoned watchtower",
      quantity: 1,
      is_selected: false,
    },
  ]);
});

test("buildInventoryItemViews falls back safely when catalog metadata is missing", async () => {
  const { buildInventoryItemViews } = await loadInventoryItemsModule();

  const views = buildInventoryItemViews({
    mystery_token: 3,
  });

  assert.deepEqual(views, [
    {
      item_id: "mystery_token",
      name: "mystery_token",
      description: "No catalog metadata.",
      quantity: 3,
      is_selected: false,
    },
  ]);
});

test("buildInventoryItemViews ignores invalid entries", async () => {
  const { buildInventoryItemViews } = await loadInventoryItemsModule();

  const views = buildInventoryItemViews({
    "": 1,
    rope: 0,
    ration: -1,
    medkit: "2",
    torch: 1,
  });

  assert.deepEqual(views, [
    {
      item_id: "torch",
      name: "torch",
      description: "a simple handheld torch for lighting dark areas",
      quantity: 1,
      is_selected: false,
    },
  ]);
});

test("buildInventoryItemViewsFromStacks derives aggregated rows from stacks and highlights the selected stack", async () => {
  const { buildInventoryItemViewsFromStacks } = await loadInventoryItemsModule();

  const views = buildInventoryItemViewsFromStacks(
    [
      { stack_id: "stk_torch_a", item_id: "torch", quantity: 1 },
      { stack_id: "stk_torch_b", item_id: "torch", quantity: 2 },
      { stack_id: "stk_key_a", item_id: "tower_key", quantity: 1 },
    ],
    {
      selectedStackId: "stk_torch_b",
      selectedItemId: "torch",
      selectionAudit: {
        mode: "item_adapter",
        reason: "deterministic_first_stack",
      },
    }
  );

  assert.deepEqual(views, [
    {
      item_id: "torch",
      name: "torch",
      description: "a simple handheld torch for lighting dark areas",
      quantity: 3,
      is_selected: true,
      stack_count: 2,
      stack_ids: ["stk_torch_a", "stk_torch_b"],
      primary_stack_id: "stk_torch_a",
      selected_stack_id: "stk_torch_b",
      selection_mode: "item_adapter",
      selection_reason: "deterministic_first_stack",
    },
    {
      item_id: "tower_key",
      name: "tower key",
      description: "the iron key that unlocks the abandoned watchtower",
      quantity: 1,
      is_selected: false,
      stack_count: 1,
      stack_ids: ["stk_key_a"],
      primary_stack_id: "stk_key_a",
      selected_stack_id: null,
      selection_mode: null,
      selection_reason: null,
    },
  ]);
});
