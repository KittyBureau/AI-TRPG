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
