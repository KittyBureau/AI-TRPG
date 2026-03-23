import { getItemCatalogEntry } from "./item_catalog.js";

function normalizeItemId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizeQuantity(value) {
  return Number.isInteger(value) && value > 0 ? value : null;
}

function normalizeStackId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizeStackView(rawStack) {
  if (!rawStack || typeof rawStack !== "object" || Array.isArray(rawStack)) {
    return null;
  }
  const stackId = normalizeStackId(rawStack.stack_id);
  const itemId = normalizeItemId(rawStack.item_id);
  const quantity = normalizeQuantity(rawStack.quantity);
  if (!stackId || !itemId || quantity === null) {
    return null;
  }
  return {
    stack_id: stackId,
    item_id: itemId,
    quantity,
  };
}

function buildBaseInventoryItemView(itemId, quantity, extra = {}) {
  const catalogEntry = getItemCatalogEntry(itemId);
  return {
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
    ...extra,
  };
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
    views.push(
      buildBaseInventoryItemView(itemId, quantity, {
        is_selected: itemId === normalizedSelectedItemId,
      })
    );
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

export function buildInventoryItemViewsFromStacks(rawStacks, options = {}) {
  const stacks = Array.isArray(rawStacks) ? rawStacks.map(normalizeStackView).filter(Boolean) : [];
  const selectedStackId = normalizeStackId(options?.selectedStackId);
  const selectedItemId = normalizeItemId(options?.selectedItemId);
  const selectionMode =
    typeof options?.selectionAudit?.mode === "string" && options.selectionAudit.mode.trim()
      ? options.selectionAudit.mode.trim()
      : "";
  const selectionReason =
    typeof options?.selectionAudit?.reason === "string" && options.selectionAudit.reason.trim()
      ? options.selectionAudit.reason.trim()
      : "";
  const grouped = new Map();

  for (const stack of stacks) {
    if (!grouped.has(stack.item_id)) {
      grouped.set(stack.item_id, {
        item_id: stack.item_id,
        quantity: 0,
        stack_ids: [],
      });
    }
    const group = grouped.get(stack.item_id);
    group.quantity += stack.quantity;
    group.stack_ids.push(stack.stack_id);
  }

  const views = [];
  for (const [itemId, group] of grouped.entries()) {
    const stackIds = [...group.stack_ids].sort((left, right) => left.localeCompare(right));
    const selectedStackForItem = selectedStackId && stackIds.includes(selectedStackId) ? selectedStackId : "";
    const isFallbackSelected =
      !selectedStackForItem && selectionMode === "item_fallback" && selectedItemId === itemId;
    views.push(
      buildBaseInventoryItemView(itemId, group.quantity, {
        is_selected: Boolean(selectedStackForItem || isFallbackSelected),
        stack_count: stackIds.length,
        stack_ids: stackIds,
        primary_stack_id: stackIds[0] || null,
        selected_stack_id: selectedStackForItem || null,
        selection_mode: selectedStackForItem || isFallbackSelected ? selectionMode || "stack_primary" : null,
        selection_reason:
          selectedStackForItem || isFallbackSelected ? selectionReason || null : null,
      })
    );
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
