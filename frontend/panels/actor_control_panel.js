import { chatTurn } from "../api/api.js";
import { getPartyActorIds, resolveActingActorId } from "../utils/acting_actor.js";
import {
  buildInventoryItemViews,
  buildInventoryItemViewsFromStacks,
} from "../utils/inventory_items.js";

function buildMovePrompt(actorId, toAreaId) {
  return `[UI_FLOW_STEP]
Return JSON with keys assistant_text, dialog_type, tool_calls.
Keep assistant_text empty.
Execute exactly one tool_call now: move.
Use args exactly:
${JSON.stringify({ actor_id: actorId, to_area_id: toAreaId })}
Do not call any additional tools.`;
}

function parseApiError(result) {
  if (result?.data && typeof result.data.detail === "string") {
    return result.data.detail;
  }
  if (typeof result?.text === "string" && result.text.trim()) {
    return result.text.trim();
  }
  return `HTTP ${result?.status ?? 500}`;
}

function captureFocusState(root) {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement) || !root.contains(active)) {
    return null;
  }
  const key = active.getAttribute("data-focus-key");
  if (!key) {
    return null;
  }
  return {
    key,
    selectionStart:
      typeof active.selectionStart === "number" ? active.selectionStart : null,
    selectionEnd:
      typeof active.selectionEnd === "number" ? active.selectionEnd : null,
  };
}

function restoreFocusState(root, snapshot) {
  if (!snapshot) {
    return;
  }
  const target = root.querySelector(`[data-focus-key="${snapshot.key}"]`);
  if (!(target instanceof HTMLElement)) {
    return;
  }
  target.focus();
  if (
    typeof snapshot.selectionStart === "number" &&
    typeof snapshot.selectionEnd === "number" &&
    "setSelectionRange" in target
  ) {
    target.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
  }
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function deriveSelectedItemIdFromState(state, actorId) {
  if (!actorId) {
    return null;
  }
  const selectedStackId =
    state?.selectedStackIdByActor && typeof state.selectedStackIdByActor === "object"
      ? state.selectedStackIdByActor[actorId]
      : null;
  const actorStacks =
    state?.inventoryStacksByActor && typeof state.inventoryStacksByActor === "object"
      ? state.inventoryStacksByActor[actorId]
      : null;
  if (Array.isArray(actorStacks) && typeof selectedStackId === "string" && selectedStackId.trim()) {
    const selectedStack = actorStacks.find(
      (stack) =>
        stack &&
        typeof stack.stack_id === "string" &&
        stack.stack_id.trim() === selectedStackId.trim()
    );
    if (selectedStack && typeof selectedStack.item_id === "string" && selectedStack.item_id.trim()) {
      return selectedStack.item_id.trim();
    }
  }
  const selectionAudit =
    state?.selectionAuditByActor && typeof state.selectionAuditByActor === "object"
      ? state.selectionAuditByActor[actorId]
      : null;
  if (selectionAudit && typeof selectionAudit === "object" && !Array.isArray(selectionAudit)) {
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

function getActorInventoryView(state, actorId, store = null) {
  const inventoryByActor =
    state?.inventoryByActor && typeof state.inventoryByActor === "object"
      ? state.inventoryByActor
      : {};
  const inventoryStacksByActor =
    state?.inventoryStacksByActor && typeof state.inventoryStacksByActor === "object"
      ? state.inventoryStacksByActor
      : {};
  if (!actorId || (!hasOwn(inventoryByActor, actorId) && !hasOwn(inventoryStacksByActor, actorId))) {
    return {
      known: false,
      items: [],
    };
  }
  const selectedStackId =
    state?.selectedStackIdByActor && typeof state.selectedStackIdByActor === "object"
      ? state.selectedStackIdByActor[actorId]
      : null;
  const actorStacks = Array.isArray(inventoryStacksByActor[actorId]) ? inventoryStacksByActor[actorId] : null;
  const selectedItemId =
    store && typeof store.getSelectedItemIdForActor === "function"
      ? store.getSelectedItemIdForActor(actorId) || ""
      : deriveSelectedItemIdFromState(state, actorId) || "";
  const selectionAudit = getActorSelectionAudit(state, actorId);
  if (Array.isArray(actorStacks)) {
    return {
      known: true,
      items: buildInventoryItemViewsFromStacks(actorStacks, {
        selectedStackId,
        selectedItemId: selectedItemId || null,
        selectionAudit,
      }),
    };
  }
  const inventory =
    inventoryByActor[actorId] && typeof inventoryByActor[actorId] === "object"
      ? inventoryByActor[actorId]
      : {};
  return {
    known: true,
    items: buildInventoryItemViews(inventory, selectedItemId || null),
  };
}

function getActorSelectionAudit(state, actorId) {
  if (!actorId || !state?.selectionAuditByActor || typeof state.selectionAuditByActor !== "object") {
    return null;
  }
  const audit = state.selectionAuditByActor[actorId];
  return audit && typeof audit === "object" && !Array.isArray(audit) ? audit : null;
}

function formatSelectionSummary(selectedItemView, selectedItemId, selectedStackId, selectionAudit) {
  if (selectedItemView) {
    const mode =
      selectionAudit && typeof selectionAudit.mode === "string" && selectionAudit.mode.trim()
        ? selectionAudit.mode.trim()
        : "stack_primary";
    const selectedStackLabel =
      selectedItemView.selected_stack_id || selectedStackId || selectedItemView.primary_stack_id || "none";
    const stackScope =
      typeof selectedItemView.stack_count === "number" && selectedItemView.stack_count > 1
        ? `, ${selectedItemView.stack_count} stacks`
        : "";
    return `Selected item: ${selectedItemView.name} (${selectedItemView.item_id}) via ${selectedStackLabel}${stackScope} [${mode}]`;
  }
  if (selectedItemId) {
    const mode =
      selectionAudit && typeof selectionAudit.mode === "string" && selectionAudit.mode.trim()
        ? selectionAudit.mode.trim()
        : "item_fallback";
    return `Selected item: ${selectedItemId} [${mode}]`;
  }
  return "Selected item: none";
}

function formatSelectionNote(selectionAudit) {
  if (selectionAudit?.mode === "item_fallback") {
    return "Selection fallback active: the next turn request will use selected_item_id until a stack can be resolved.";
  }
  if (
    Array.isArray(selectionAudit?.candidate_stack_ids) &&
    selectionAudit.candidate_stack_ids.length > 1
  ) {
    return `Selection uses selected_stack_id. Multiple stacks are present; the current adapter path picked ${selectionAudit.selected_stack_id}.`;
  }
  return "Selection is stored per actor and sent as selected_stack_id by default. selected_item_id is fallback-only.";
}

export function buildTurnPayload(state, actorId, userInput, store) {
  const payload = {
    campaign_id: state.campaignId,
    user_input: userInput,
    execution: { actor_id: actorId },
  };
  const contextHints =
    store && typeof store.buildTurnContextHintsForActor === "function"
      ? store.buildTurnContextHintsForActor(actorId)
      : null;
  if (contextHints && typeof contextHints === "object" && !Array.isArray(contextHints)) {
    const hintEntries = Object.entries(contextHints).filter(
      ([, value]) => typeof value === "string" && value.trim()
    );
    if (hintEntries.length > 0) {
      payload.context_hints = Object.fromEntries(hintEntries.map(([key, value]) => [key, value.trim()]));
    }
  }
  return payload;
}

export function initPanel(store) {
  const mount = document.getElementById("actorControlPanel");
  if (!mount) {
    return;
  }

  const uiState = {
    userInput: "",
    moveToAreaId: "",
  };

  async function refreshCampaignState(campaignId) {
    if (!campaignId || typeof store.refreshCampaign !== "function") {
      return true;
    }
    const state = store.getState();
    const refreshResult = await store.refreshCampaign(campaignId, state.baseUrl);
    if (!refreshResult.ok) {
      store.setStatusMessage(`Refresh campaign failed: ${parseApiError(refreshResult)}`);
      return false;
    }
    if (typeof store.refreshCampaignWorldPreview === "function") {
      await store.refreshCampaignWorldPreview(campaignId, state.baseUrl, { emit: true });
    }
    return true;
  }

  async function runTurn() {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    if (state.baseUrl && typeof store.checkBackendReady === "function") {
      const readiness = await store.checkBackendReady(state.baseUrl, { silent: false });
      if (readiness.ready === false) {
        return;
      }
    }
    const actorId = resolveActingActorId(state);
    if (!actorId) {
      store.setStatusMessage("Party empty / no actor selected.");
      return;
    }
    const userInput = uiState.userInput.trim();
    if (!userInput) {
      store.setStatusMessage("Turn input is required.");
      return;
    }
    const payload = buildTurnPayload(state, actorId, userInput, store);
    const result = await chatTurn(state.baseUrl, payload);
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Turn failed: ${parseApiError(result)}`);
      store.setDebugResponseText(result.text || "");
      return;
    }
    store.recordTurnResult(result.data, JSON.stringify(result.data, null, 2));
    const refreshed = await refreshCampaignState(state.campaignId);
    if (!refreshed) {
      return;
    }
    const effectiveActorId =
      typeof result.data.effective_actor_id === "string" && result.data.effective_actor_id.trim()
        ? result.data.effective_actor_id.trim()
        : actorId;
    store.setStatusMessage(`Turn completed as ${effectiveActorId}.`);
  }

  async function runMove() {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    if (state.baseUrl && typeof store.checkBackendReady === "function") {
      const readiness = await store.checkBackendReady(state.baseUrl, { silent: false });
      if (readiness.ready === false) {
        return;
      }
    }
    const actorId = resolveActingActorId(state);
    const toAreaId = uiState.moveToAreaId.trim();
    if (!actorId || !toAreaId) {
      if (!actorId) {
        store.setStatusMessage("Party empty / no actor selected.");
      } else {
        store.setStatusMessage("to_area_id is required.");
      }
      return;
    }
    const payload = {
      campaign_id: state.campaignId,
      user_input: buildMovePrompt(actorId, toAreaId),
      execution: { actor_id: actorId },
    };
    const result = await chatTurn(state.baseUrl, payload);
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Move failed: ${parseApiError(result)}`);
      store.setDebugResponseText(result.text || "");
      return;
    }
    store.recordTurnResult(result.data, JSON.stringify(result.data, null, 2));
    const refreshed = await refreshCampaignState(state.campaignId);
    if (!refreshed) {
      return;
    }
    const effectiveActorId =
      typeof result.data.effective_actor_id === "string" && result.data.effective_actor_id.trim()
        ? result.data.effective_actor_id.trim()
        : actorId;
    store.setStatusMessage(`Move completed as ${effectiveActorId}.`);
  }

  function render() {
    const state = store.getState();
    const focusSnapshot = captureFocusState(mount);
    const party = getPartyActorIds(state);
    const actingActorId = resolveActingActorId(state);
    const canAct = Boolean(actingActorId);
    const inventoryView = getActorInventoryView(state, actingActorId, store);
    const selectedStackId =
      actingActorId && state.selectedStackIdByActor
        ? state.selectedStackIdByActor[actingActorId] || null
        : null;
    const selectedItemId =
      actingActorId && typeof store.getSelectedItemIdForActor === "function"
        ? store.getSelectedItemIdForActor(actingActorId)
        : deriveSelectedItemIdFromState(state, actingActorId);
    const selectionAudit = getActorSelectionAudit(state, actingActorId);
    const selectedItemView =
      inventoryView.known && Array.isArray(inventoryView.items)
        ? inventoryView.items.find((item) => item.is_selected) || null
        : null;

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Actor Control";
    mount.appendChild(title);

    const actingAs = document.createElement("div");
    actingAs.className = "row";
    actingAs.textContent = `Acting as: ${actingActorId || "none"}`;
    mount.appendChild(actingAs);

    const actorField = document.createElement("label");
    actorField.className = "field";
    actorField.innerHTML = '<span class="field-label">Actor</span>';
    const actorSelect = document.createElement("select");
    actorSelect.setAttribute("data-focus-key", "actor-select");
    const actorEmpty = document.createElement("option");
    actorEmpty.value = "";
    actorEmpty.textContent = "Select actor";
    actorSelect.appendChild(actorEmpty);
    for (const actorId of party) {
      const option = document.createElement("option");
      option.value = actorId;
      option.textContent = actorId;
      option.selected = actorId === actingActorId;
      actorSelect.appendChild(option);
    }
    actorSelect.disabled = !party.length;
    actorSelect.addEventListener("change", async () => {
      const nextActorId = actorSelect.value.trim();
      if (!nextActorId || nextActorId === actingActorId) {
        return;
      }
      const result = await store.selectActiveActor(nextActorId);
      if (!result.ok) {
        store.setStatusMessage(`Set active actor failed: ${parseApiError(result)}`);
      }
    });
    actorField.appendChild(actorSelect);
    mount.appendChild(actorField);

    if (!canAct) {
      const emptyHint = document.createElement("div");
      emptyHint.className = "note";
      emptyHint.textContent = "Party empty / no actor selected.";
      mount.appendChild(emptyHint);
    }

    const inventoryTitle = document.createElement("h3");
    inventoryTitle.textContent = "Inventory";
    mount.appendChild(inventoryTitle);

    const selectionRow = document.createElement("div");
    selectionRow.className = "note";
    selectionRow.textContent = formatSelectionSummary(
      selectedItemView,
      selectedItemId,
      selectedStackId,
      selectionAudit
    );
    mount.appendChild(selectionRow);

    const inventoryNote = document.createElement("div");
    inventoryNote.className = "note";
    inventoryNote.textContent = formatSelectionNote(selectionAudit);
    mount.appendChild(inventoryNote);

    if (!canAct) {
      const inventoryEmpty = document.createElement("div");
      inventoryEmpty.className = "note";
      inventoryEmpty.textContent = "Select an actor to inspect inventory.";
      mount.appendChild(inventoryEmpty);
    } else if (!inventoryView.known) {
      const inventoryUnknown = document.createElement("div");
      inventoryUnknown.className = "note";
      inventoryUnknown.textContent =
        "Inventory snapshot unavailable yet. It will appear after a successful turn response.";
      mount.appendChild(inventoryUnknown);
    } else if (!inventoryView.items.length) {
      const inventoryNone = document.createElement("div");
      inventoryNone.className = "note";
      inventoryNone.textContent = "No items in inventory.";
      mount.appendChild(inventoryNone);
    } else {
      const inventoryList = document.createElement("div");
      inventoryList.className = "stack";
      for (const item of inventoryView.items) {
        const itemButton = document.createElement("button");
        itemButton.type = "button";
        itemButton.className =
          item.is_selected ? "inventory-item selected" : "inventory-item";
        itemButton.setAttribute("aria-pressed", item.is_selected ? "true" : "false");
        itemButton.addEventListener("click", () => {
          const selected = store.setSelectedItemForActor(actingActorId, item.item_id);
          if (!selected) {
            store.setStatusMessage(`Failed to select item: ${item.item_id}`);
          }
        });

        const itemHeader = document.createElement("div");
        itemHeader.className = "inventory-item-header";

        const itemName = document.createElement("div");
        itemName.className = "inventory-item-name";
        itemName.textContent = item.name;
        itemHeader.appendChild(itemName);

        const itemQuantity = document.createElement("div");
        itemQuantity.className = "inventory-item-quantity";
        itemQuantity.textContent = `x${item.quantity}`;
        itemHeader.appendChild(itemQuantity);

        if (item.is_selected) {
          const selectedBadge = document.createElement("div");
          selectedBadge.className = "inventory-item-badge";
          selectedBadge.textContent = "Selected";
          itemHeader.appendChild(selectedBadge);
        }

        const itemDescription = document.createElement("div");
        itemDescription.className = "inventory-item-description";
        itemDescription.textContent = item.description;

        const itemMeta = document.createElement("div");
        itemMeta.className = "inventory-item-meta";
        const itemMetaParts = [`item_id: ${item.item_id}`];
        if (typeof item.stack_count === "number" && item.stack_count > 0) {
          itemMetaParts.push(`stacks: ${item.stack_count}`);
        }
        if (item.is_selected && item.selected_stack_id) {
          itemMetaParts.push(`selected_stack_id: ${item.selected_stack_id}`);
        } else if (item.primary_stack_id) {
          itemMetaParts.push(`primary_stack_id: ${item.primary_stack_id}`);
        }
        if (item.selection_reason) {
          itemMetaParts.push(`selection_rule: ${item.selection_reason}`);
        }
        itemMeta.textContent = itemMetaParts.join(" | ");

        itemButton.appendChild(itemHeader);
        itemButton.appendChild(itemDescription);
        itemButton.appendChild(itemMeta);
        if (Array.isArray(item.stack_ids) && item.stack_ids.length > 1) {
          const itemStacks = document.createElement("div");
          itemStacks.className = "inventory-item-meta";
          itemStacks.textContent = `stack_ids: ${item.stack_ids.join(", ")}`;
          itemButton.appendChild(itemStacks);
        }
        inventoryList.appendChild(itemButton);
      }
      mount.appendChild(inventoryList);
    }

    const turnField = document.createElement("label");
    turnField.className = "field";
    turnField.innerHTML = '<span class="field-label">Turn Input</span>';
    const turnInput = document.createElement("textarea");
    turnInput.setAttribute("data-focus-key", "turn-input");
    turnInput.rows = 3;
    turnInput.placeholder = "Describe action...";
    turnInput.value = uiState.userInput;
    turnInput.addEventListener("input", () => {
      uiState.userInput = turnInput.value;
    });
    turnField.appendChild(turnInput);
    mount.appendChild(turnField);

    const turnButton = document.createElement("button");
    turnButton.className = "primary";
    turnButton.textContent = "Send Turn";
    turnButton.disabled = !canAct;
    turnButton.addEventListener("click", runTurn);
    mount.appendChild(turnButton);

    const moveField = document.createElement("label");
    moveField.className = "field";
    moveField.innerHTML = '<span class="field-label">Move to area_id</span>';
    const moveInput = document.createElement("input");
    moveInput.setAttribute("data-focus-key", "move-input");
    moveInput.placeholder = "area_002";
    moveInput.value = uiState.moveToAreaId;
    moveInput.addEventListener("input", () => {
      uiState.moveToAreaId = moveInput.value;
    });
    moveField.appendChild(moveInput);
    mount.appendChild(moveField);

    const moveButton = document.createElement("button");
    moveButton.textContent = "Move";
    moveButton.disabled = !canAct;
    moveButton.addEventListener("click", runMove);
    mount.appendChild(moveButton);

    restoreFocusState(mount, focusSnapshot);
  }

  render();
  store.subscribe(render);
}
