import { getItemCatalogEntry } from "./item_catalog.js";

function normalizeItemId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizeQuantity(value) {
  return Number.isInteger(value) && value > 0 ? value : null;
}

export function buildInventoryItemViews(rawInventory, selectedItemId = null) {
  const inventory =
    rawInventory && typeof rawInventory === "object" && !Array.isArray(rawInventory)
      ? rawInventory
      : {};
  const normalizedSelectedItemId = normalizeItemId(selectedItemId);
  const views = [];

  for (const [rawItemId, rawQuantity] of Object.entries(inventory)) {
    const itemId = normalizeItemId(rawItemId);
    const quantity = normalizeQuantity(rawQuantity);
    if (!itemId || quantity === null) {
      continue;
    }
    const catalogEntry = getItemCatalogEntry(itemId);
    views.push({
      item_id: itemId,
      name:
        catalogEntry && typeof catalogEntry.name === "string" && catalogEntry.name.trim()
          ? catalogEntry.name.trim()
          : itemId,
      description:
        catalogEntry &&
        typeof catalogEntry.description === "string" &&
        catalogEntry.description.trim()
          ? catalogEntry.description.trim()
          : "No catalog metadata.",
      quantity,
      is_selected: itemId === normalizedSelectedItemId,
    });
  }

  views.sort((left, right) => {
    const leftName = left.name.toLocaleLowerCase();
    const rightName = right.name.toLocaleLowerCase();
    if (leftName !== rightName) {
      return leftName.localeCompare(rightName);
    }
    return left.item_id.localeCompare(right.item_id);
  });
  return views;
}
