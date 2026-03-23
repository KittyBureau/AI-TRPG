import {
  extractDebugResourcesFromResponseText,
  formatResourceEntry,
  RESOURCE_CATEGORIES,
} from "../utils/debug_resources.js";

function normalizeActorId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizeStackView(rawStack) {
  if (!rawStack || typeof rawStack !== "object" || Array.isArray(rawStack)) {
    return null;
  }
  const stackId = typeof rawStack.stack_id === "string" && rawStack.stack_id.trim()
    ? rawStack.stack_id.trim()
    : "";
  const itemId = typeof rawStack.item_id === "string" && rawStack.item_id.trim()
    ? rawStack.item_id.trim()
    : "";
  const quantity = Number(rawStack.quantity);
  if (!stackId || !itemId || !Number.isInteger(quantity) || quantity <= 0) {
    return null;
  }
  return {
    stack_id: stackId,
    item_id: itemId,
    quantity,
  };
}

function findActiveActorStacks(state, actorId) {
  if (!actorId) {
    return [];
  }
  const inventoryStacksByActor =
    state?.inventoryStacksByActor && typeof state.inventoryStacksByActor === "object"
      ? state.inventoryStacksByActor
      : {};
  if (Array.isArray(inventoryStacksByActor[actorId])) {
    return inventoryStacksByActor[actorId].map(normalizeStackView).filter(Boolean);
  }
  const stateSummary =
    state?.stateSummary && typeof state.stateSummary === "object" ? state.stateSummary : null;
  if (Array.isArray(stateSummary?.active_actor_inventory_stacks)) {
    return stateSummary.active_actor_inventory_stacks.map(normalizeStackView).filter(Boolean);
  }
  const summaryStacks =
    stateSummary?.inventory_stacks && typeof stateSummary.inventory_stacks === "object"
      ? stateSummary.inventory_stacks[actorId]
      : null;
  return Array.isArray(summaryStacks) ? summaryStacks.map(normalizeStackView).filter(Boolean) : [];
}

function resolveSelectedItemId(state, actorId, selectedStackId, selectionAudit) {
  if (!actorId) {
    return null;
  }
  const inventoryStacks = findActiveActorStacks(state, actorId);
  if (selectedStackId) {
    const selectedStack = inventoryStacks.find((stack) => stack.stack_id === selectedStackId);
    if (selectedStack) {
      return selectedStack.item_id;
    }
  }
  if (
    selectionAudit &&
    typeof selectionAudit === "object" &&
    !Array.isArray(selectionAudit)
  ) {
    if (
      typeof selectionAudit.requested_item_id === "string" &&
      selectionAudit.requested_item_id.trim()
    ) {
      return selectionAudit.requested_item_id.trim();
    }
    if (
      typeof selectionAudit.selected_item_id === "string" &&
      selectionAudit.selected_item_id.trim()
    ) {
      return selectionAudit.selected_item_id.trim();
    }
  }
  return null;
}

export function buildSelectionDebugView(state) {
  const actorId = normalizeActorId(state?.campaign?.active_actor_id);
  const selectedStackId =
    actorId &&
    state?.selectedStackIdByActor &&
    typeof state.selectedStackIdByActor === "object"
      ? state.selectedStackIdByActor[actorId] || null
      : null;
  const selectionAudit =
    actorId &&
    state?.selectionAuditByActor &&
    typeof state.selectionAuditByActor === "object"
      ? state.selectionAuditByActor[actorId] || null
      : null;
  const submitSelectionAudit =
    actorId &&
    state?.submitSelectionAuditByActor &&
    typeof state.submitSelectionAuditByActor === "object"
      ? state.submitSelectionAuditByActor[actorId] || null
      : null;
  const inventoryStacks = findActiveActorStacks(state, actorId);
  const selectedItemId = resolveSelectedItemId(
    state,
    actorId,
    selectedStackId,
    selectionAudit
  );
  return {
    actor_id: actorId || null,
    selected_stack_id: selectedStackId,
    selected_item_id: selectedItemId,
    selection_mode: selectionAudit?.mode || null,
    submit_mode: submitSelectionAudit?.mode || null,
    fallback_active:
      selectionAudit?.mode === "item_fallback" || submitSelectionAudit?.mode === "item_fallback",
    selection_audit: selectionAudit,
    submit_selection_audit: submitSelectionAudit,
    inventory_stacks: inventoryStacks,
  };
}

function formatStackDebugEntry(stack) {
  const normalized = normalizeStackView(stack);
  if (!normalized) {
    return "(invalid stack)";
  }
  return `${normalized.stack_id}: ${normalized.item_id} x${normalized.quantity}`;
}

export function initPanel(store) {
  const mount = document.getElementById("debugPanel");
  if (!mount) {
    return;
  }

  function formatBackendMessage(state) {
    const reason = state.backend?.reason || "unknown";
    if (reason === "config_missing") {
      return "Backend credentials config is missing. Create storage/config/llm_config.json.";
    }
    if (reason === "keyring_missing") {
      return "Backend keyring is missing. Create storage/secrets/keyring.json.";
    }
    if (reason === "credentials_unavailable") {
      return "Backend credentials are not ready. Check llm_config.json and keyring.json.";
    }
    return "Backend is waiting for credential unlock. Run `python -m backend.tools.unlock_keyring` locally, then retry.";
  }

  function render() {
    const state = store.getState();
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Debug";
    mount.appendChild(title);

    const status = document.createElement("div");
    status.className = "row";
    status.textContent = `Status: ${state.statusMessage || "Idle"}`;
    mount.appendChild(status);

    if (state.backend?.ready === false) {
      const backendNote = document.createElement("div");
      backendNote.className = "note";
      backendNote.textContent = formatBackendMessage(state);
      mount.appendChild(backendNote);
    }

    const latestTurn =
      Array.isArray(state.turnHistory) && state.turnHistory.length
        ? state.turnHistory[state.turnHistory.length - 1]
        : null;
    const selectionDebugView = buildSelectionDebugView(state);
    const actionsTitle = document.createElement("h3");
    actionsTitle.textContent = "Applied Actions";
    mount.appendChild(actionsTitle);

    const actions = Array.isArray(latestTurn?.applied_actions) ? latestTurn.applied_actions : [];
    if (!actions.length) {
      const emptyActions = document.createElement("div");
      emptyActions.className = "note";
      emptyActions.textContent = "No applied actions in latest turn.";
      mount.appendChild(emptyActions);
    } else {
      for (const action of actions) {
        const row = document.createElement("div");
        row.className = "row";
        const tool = typeof action?.tool === "string" ? action.tool : "unknown";
        const result = action?.result && typeof action.result === "object" ? action.result : {};
        row.textContent = `${tool}: ${JSON.stringify(result)}`;
        mount.appendChild(row);
      }
    }

    const selectionTitle = document.createElement("h3");
    selectionTitle.textContent = "Selection";
    mount.appendChild(selectionTitle);

    const selectionRows = [
      `actor_id: ${selectionDebugView.actor_id || "none"}`,
      `selected_stack_id: ${selectionDebugView.selected_stack_id || "none"}`,
      `selected_item_id: ${selectionDebugView.selected_item_id || "none"}`,
      `selection_mode: ${selectionDebugView.selection_mode || "none"}`,
      `submit_mode: ${selectionDebugView.submit_mode || "none"}`,
      `fallback_active: ${selectionDebugView.fallback_active ? "yes" : "no"}`,
    ];
    for (const line of selectionRows) {
      const row = document.createElement("div");
      row.className = "row";
      row.textContent = line;
      mount.appendChild(row);
    }

    if (selectionDebugView.selection_audit || selectionDebugView.submit_selection_audit) {
      const selectionAuditPre = document.createElement("pre");
      selectionAuditPre.className = "raw";
      selectionAuditPre.textContent = JSON.stringify(
        {
          selection_audit: selectionDebugView.selection_audit,
          submit_selection_audit: selectionDebugView.submit_selection_audit,
        },
        null,
        2
      );
      mount.appendChild(selectionAuditPre);
    }

    const stacksTitle = document.createElement("h3");
    stacksTitle.textContent = "Active Inventory Stacks";
    mount.appendChild(stacksTitle);

    if (!selectionDebugView.inventory_stacks.length) {
      const emptyStacks = document.createElement("div");
      emptyStacks.className = "note";
      emptyStacks.textContent = "No stack snapshot available for the active actor.";
      mount.appendChild(emptyStacks);
    } else {
      for (const stack of selectionDebugView.inventory_stacks) {
        const row = document.createElement("div");
        row.className = "row";
        row.textContent = formatStackDebugEntry(stack);
        mount.appendChild(row);
      }
    }

    const resourcesTitle = document.createElement("h3");
    resourcesTitle.textContent = "Debug Resources";
    mount.appendChild(resourcesTitle);

    const resourcesView = extractDebugResourcesFromResponseText(
      state.debug?.responseText || ""
    );
    const resourcesNote = document.createElement("div");
    resourcesNote.className = "note";
    if (!resourcesView.available) {
      resourcesNote.textContent = resourcesView.reason || "trace disabled / no debug";
      mount.appendChild(resourcesNote);
    } else {
      resourcesNote.textContent =
        resourcesView.source === "resources"
          ? "Source: debug.resources"
          : "Source: legacy debug fields";
      mount.appendChild(resourcesNote);

      for (const category of RESOURCE_CATEGORIES) {
        const entries = Array.isArray(resourcesView.resources?.[category])
          ? resourcesView.resources[category]
          : [];
        const sectionTitle = document.createElement("div");
        sectionTitle.className = "note";
        sectionTitle.textContent = `${category} (${entries.length})`;
        mount.appendChild(sectionTitle);
        if (!entries.length) {
          const empty = document.createElement("div");
          empty.className = "row note";
          empty.textContent = "(empty)";
          mount.appendChild(empty);
          continue;
        }
        for (const entry of entries) {
          const row = document.createElement("div");
          row.className = "row";
          row.textContent = formatResourceEntry(category, entry);
          mount.appendChild(row);
        }
      }
    }

    const actionsBar = document.createElement("div");
    actionsBar.className = "inline";
    const clear = document.createElement("button");
    clear.textContent = "Clear Response";
    clear.addEventListener("click", () => {
      store.setDebugResponseText("");
    });
    actionsBar.appendChild(clear);
    mount.appendChild(actionsBar);

    const rawTitle = document.createElement("h3");
    rawTitle.textContent = "Raw Response";
    mount.appendChild(rawTitle);

    const pre = document.createElement("pre");
    pre.className = "raw";
    pre.textContent = state.debug?.responseText || "No API response yet.";
    mount.appendChild(pre);
  }

  render();
  store.subscribe(render);
}
