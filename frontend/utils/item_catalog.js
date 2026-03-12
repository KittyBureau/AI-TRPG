// Frontend static serving does not expose repo-sibling resources/, so this mirrors
// resources/data/items_catalog_v1.json for read-only inventory presentation.
const ITEM_CATALOG = Object.freeze({
  rusty_key: Object.freeze({
    name: "rusty key",
    description: "an old iron key, possibly opens ancient locks",
  }),
  torch: Object.freeze({
    name: "torch",
    description: "a simple handheld torch for lighting dark areas",
  }),
  tower_key: Object.freeze({
    name: "tower key",
    description: "the iron key that unlocks the abandoned watchtower",
  }),
});

function normalizeItemId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

export function getItemCatalogEntry(itemId) {
  const normalizedItemId = normalizeItemId(itemId);
  if (!normalizedItemId) {
    return null;
  }
  const entry = ITEM_CATALOG[normalizedItemId];
  return entry && typeof entry === "object" ? entry : null;
}

export { ITEM_CATALOG };
