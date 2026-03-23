function actorValue(summary, key, actorId) {
  if (!summary || typeof summary !== "object") {
    return null;
  }
  const group = summary[key];
  if (!group || typeof group !== "object") {
    return null;
  }
  return actorId in group ? group[actorId] : null;
}

function actorInventory(summary, actorId) {
  if (!summary || typeof summary !== "object") {
    return {};
  }
  const inventories = summary.inventories;
  if (!inventories || typeof inventories !== "object") {
    return {};
  }
  const inventory = inventories[actorId];
  return inventory && typeof inventory === "object" ? inventory : {};
}

function actorInventoryStacks(summary, actorId) {
  if (!summary || typeof summary !== "object") {
    return [];
  }
  if (
    summary.active_actor_id === actorId &&
    Array.isArray(summary.active_actor_inventory_stacks)
  ) {
    return summary.active_actor_inventory_stacks;
  }
  const inventoryStacks = summary.inventory_stacks;
  if (!inventoryStacks || typeof inventoryStacks !== "object") {
    return [];
  }
  const actorStacks = inventoryStacks[actorId];
  return Array.isArray(actorStacks) ? actorStacks : [];
}

function inventoryChanges(beforeInventory, afterInventory) {
  const keys = new Set([
    ...Object.keys(beforeInventory || {}),
    ...Object.keys(afterInventory || {}),
  ]);
  const changes = [];
  for (const key of [...keys].sort()) {
    const before = typeof beforeInventory[key] === "number" ? beforeInventory[key] : 0;
    const after = typeof afterInventory[key] === "number" ? afterInventory[key] : 0;
    if (before !== after) {
      changes.push({
        item_id: key,
        before,
        after,
        delta: after - before,
      });
    }
  }
  return changes;
}

function inventoryStackChanges(beforeStacks, afterStacks) {
  const beforeById = new Map();
  const afterById = new Map();
  for (const stack of Array.isArray(beforeStacks) ? beforeStacks : []) {
    if (stack && typeof stack === "object" && typeof stack.stack_id === "string") {
      beforeById.set(stack.stack_id, stack);
    }
  }
  for (const stack of Array.isArray(afterStacks) ? afterStacks : []) {
    if (stack && typeof stack === "object" && typeof stack.stack_id === "string") {
      afterById.set(stack.stack_id, stack);
    }
  }
  const keys = new Set([...beforeById.keys(), ...afterById.keys()]);
  const changes = [];
  for (const stackId of [...keys].sort()) {
    const before = beforeById.get(stackId) || null;
    const after = afterById.get(stackId) || null;
    const beforeQuantity = Number.isInteger(before?.quantity) ? before.quantity : 0;
    const afterQuantity = Number.isInteger(after?.quantity) ? after.quantity : 0;
    const beforeItemId = before && typeof before.item_id === "string" ? before.item_id : "";
    const afterItemId = after && typeof after.item_id === "string" ? after.item_id : "";
    if (beforeQuantity !== afterQuantity || beforeItemId !== afterItemId) {
      changes.push({
        stack_id: stackId,
        item_id: afterItemId || beforeItemId || "",
        before_quantity: beforeQuantity,
        after_quantity: afterQuantity,
        delta: afterQuantity - beforeQuantity,
      });
    }
  }
  return changes;
}

export function buildDelta(previousSummary, nextSummary, actorId) {
  const beforePosition = actorValue(previousSummary, "positions", actorId);
  const afterPosition = actorValue(nextSummary, "positions", actorId);
  const beforeHp = actorValue(previousSummary, "hp", actorId);
  const afterHp = actorValue(nextSummary, "hp", actorId);
  const beforeState = actorValue(previousSummary, "character_states", actorId);
  const afterState = actorValue(nextSummary, "character_states", actorId);

  const beforeInventory = actorInventory(previousSummary, actorId);
  const afterInventory = actorInventory(nextSummary, actorId);
  const changes = inventoryChanges(beforeInventory, afterInventory);
  const beforeInventoryStacks = actorInventoryStacks(previousSummary, actorId);
  const afterInventoryStacks = actorInventoryStacks(nextSummary, actorId);
  const stackChanges = inventoryStackChanges(beforeInventoryStacks, afterInventoryStacks);

  const delta = {
    actor_id: actorId,
    changed: false,
    position: {
      before: beforePosition,
      after: afterPosition,
      changed: beforePosition !== afterPosition,
    },
    hp: {
      before: beforeHp,
      after: afterHp,
      changed: beforeHp !== afterHp,
    },
    character_state: {
      before: beforeState,
      after: afterState,
      changed: beforeState !== afterState,
    },
    inventory: {
      before: beforeInventory,
      after: afterInventory,
      changed: changes.length > 0,
      changes,
      stacks_before: beforeInventoryStacks,
      stacks_after: afterInventoryStacks,
      stack_changes: stackChanges,
    },
    error: null,
  };

  delta.changed =
    delta.position.changed ||
    delta.hp.changed ||
    delta.character_state.changed ||
    delta.inventory.changed ||
    stackChanges.length > 0;

  return delta;
}

export function buildErrorDelta(previousSummary, actorId, errorType, message, status = null) {
  const delta = buildDelta(previousSummary, previousSummary, actorId);
  delta.error = {
    type: errorType,
    status,
    message,
  };
  return delta;
}

export function renderDeltaLines(delta) {
  if (!delta || typeof delta !== "object") {
    return ["no delta"];
  }

  const lines = [];
  if (delta.position?.changed) {
    lines.push(`moved: ${String(delta.position.before)} -> ${String(delta.position.after)}`);
  }
  if (delta.hp?.changed) {
    lines.push(`hp: ${String(delta.hp.before)} -> ${String(delta.hp.after)}`);
  }
  if (delta.character_state?.changed) {
    lines.push(
      `state: ${String(delta.character_state.before)} -> ${String(delta.character_state.after)}`
    );
  }
  if (delta.inventory?.changed && Array.isArray(delta.inventory.changes)) {
    for (const change of delta.inventory.changes) {
      const sign = change.delta >= 0 ? "+" : "";
      lines.push(`inventory: ${change.item_id} (${sign}${change.delta})`);
    }
  }
  if (Array.isArray(delta.inventory?.stack_changes) && delta.inventory.stack_changes.length) {
    for (const change of delta.inventory.stack_changes) {
      const sign = change.delta >= 0 ? "+" : "";
      lines.push(`inventory_stack: ${change.stack_id} ${change.item_id} (${sign}${change.delta})`);
    }
  }
  if (delta.error) {
    lines.push(`error: ${delta.error.type} (${delta.error.status ?? "n/a"})`);
  }

  if (lines.length === 0) {
    lines.push("no tracked changes");
  }
  return lines;
}
