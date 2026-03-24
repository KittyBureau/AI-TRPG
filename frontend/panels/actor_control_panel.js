import { chatTurn } from "../api/api.js";
import { getPartyActorIds, resolveActingActorId } from "../utils/acting_actor.js";
import {
  buildInventoryItemViews,
  buildInventoryItemViewsFromStacks,
} from "../utils/inventory_items.js";
import {
  sceneEntitySupportsAction,
  selectedTargetActionLabels,
} from "../utils/scene_targets.js";

export function buildSceneActionPrompt(actorId, action, targetId) {
  return `[UI_FLOW_STEP]
Return JSON with keys assistant_text, dialog_type, tool_calls.
Keep assistant_text empty.
Execute exactly one tool_call now: scene_action.
Use args exactly:
${JSON.stringify({ actor_id: actorId, action, target_id: targetId, params: {} })}
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
  const selectionAudit =
    state?.selectionAuditByActor && typeof state.selectionAuditByActor === "object"
      ? state.selectionAuditByActor[actorId] || null
      : null;
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

function selectedItemSummary(selectedItemView) {
  if (!selectedItemView) {
    return "Selected inventory item: none";
  }
  return `Selected inventory item: ${selectedItemView.name} (${selectedItemView.item_id})`;
}

function selectedTargetSummary(selectedSceneTarget) {
  if (!selectedSceneTarget) {
    return "Selected scene target: none";
  }
  const actionLabels = selectedTargetActionLabels(selectedSceneTarget);
  const actionText = actionLabels.length ? ` | available: ${actionLabels.join(", ")}` : "";
  return `Selected scene target: ${selectedSceneTarget.label} (${selectedSceneTarget.id})${actionText}`;
}

function selectedSceneTargetSupportsAction(selectedSceneTarget, action) {
  return sceneEntitySupportsAction(selectedSceneTarget, action);
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
  };

  async function refreshPlayState() {
    const state = store.getState();
    if (!state.campaignId || typeof store.refreshCampaign !== "function") {
      return true;
    }
    const refreshResult = await store.refreshCampaign(state.campaignId, state.baseUrl);
    if (!refreshResult.ok) {
      store.setStatusMessage(`Refresh campaign failed: ${parseApiError(refreshResult)}`);
      return false;
    }
    if (typeof store.refreshCampaignWorldPreview === "function") {
      await store.refreshCampaignWorldPreview(state.campaignId, state.baseUrl, { emit: true });
    }
    if (typeof store.refreshMapView === "function") {
      await store.refreshMapView(state.campaignId, store.getState().campaign.active_actor_id, state.baseUrl, {
        emit: true,
      });
    }
    return true;
  }

  async function submitPayload(payload, successPrefix) {
    const state = store.getState();
    const result = await chatTurn(state.baseUrl, payload);
    if (!result.ok || !result.data) {
      store.setStatusMessage(`${successPrefix} failed: ${parseApiError(result)}`);
      store.setDebugResponseText(result.text || "");
      return false;
    }
    store.recordTurnResult(result.data, JSON.stringify(result.data, null, 2));
    const refreshed = await refreshPlayState();
    if (!refreshed) {
      return false;
    }
    const effectiveActorId =
      typeof result.data.effective_actor_id === "string" && result.data.effective_actor_id.trim()
        ? result.data.effective_actor_id.trim()
        : state.campaign.active_actor_id;
    store.setStatusMessage(`${successPrefix} completed as ${effectiveActorId}.`);
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
    await submitPayload(buildTurnPayload(state, actorId, userInput, store), "Turn");
  }

  async function runSelectedSceneAction(action, successPrefix) {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    const actorId = resolveActingActorId(state);
    if (!actorId) {
      store.setStatusMessage("Party empty / no actor selected.");
      return;
    }
    const selectedSceneTarget =
      typeof store.getSelectedSceneTargetForActor === "function"
        ? store.getSelectedSceneTargetForActor(actorId)
        : null;
    if (!selectedSceneTarget?.id) {
      store.setStatusMessage("Select a scene target first.");
      return;
    }
    if (!selectedSceneTargetSupportsAction(selectedSceneTarget, action)) {
      store.setStatusMessage(`Selected target does not support ${action}.`);
      return;
    }
    const payload = buildTurnPayload(
      state,
      actorId,
      buildSceneActionPrompt(actorId, action, selectedSceneTarget.id),
      store
    );
    await submitPayload(payload, successPrefix);
  }

  function render() {
    const state = store.getState();
    const focusSnapshot = captureFocusState(mount);
    const party = getPartyActorIds(state);
    const actingActorId = resolveActingActorId(state);
    const canAct = Boolean(actingActorId);
    const inventoryView = getActorInventoryView(state, actingActorId, store);
    const selectedItemView =
      inventoryView.known && Array.isArray(inventoryView.items)
        ? inventoryView.items.find((item) => item.is_selected) || null
        : null;
    const selectedSceneTarget =
      canAct && typeof store.getSelectedSceneTargetForActor === "function"
        ? store.getSelectedSceneTargetForActor(actingActorId)
        : null;

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Actions";
    mount.appendChild(title);

    const actorField = document.createElement("label");
    actorField.className = "field";
    actorField.innerHTML = '<span class="field-label">Acting As</span>';
    const actorSelect = document.createElement("select");
    actorSelect.setAttribute("data-focus-key", "actor-select");
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

    const selectedTarget = document.createElement("div");
    selectedTarget.className = "selection-summary";
    selectedTarget.textContent = selectedTargetSummary(selectedSceneTarget);
    mount.appendChild(selectedTarget);

    const selectedInventory = document.createElement("div");
    selectedInventory.className = "selection-summary";
    selectedInventory.textContent = selectedItemSummary(selectedItemView);
    mount.appendChild(selectedInventory);

    const turnField = document.createElement("label");
    turnField.className = "field";
    turnField.innerHTML = '<span class="field-label">What do you do?</span>';
    const turnInput = document.createElement("textarea");
    turnInput.setAttribute("data-focus-key", "turn-input");
    turnInput.rows = 4;
    turnInput.placeholder = "Talk, inspect, use an item, or describe your next move...";
    turnInput.value = uiState.userInput;
    turnInput.addEventListener("input", () => {
      uiState.userInput = turnInput.value;
    });
    turnField.appendChild(turnInput);
    mount.appendChild(turnField);

    const actionsBar = document.createElement("div");
    actionsBar.className = "action-bar";

    const turnButton = document.createElement("button");
    turnButton.className = "primary";
    turnButton.textContent = "Send Turn";
    turnButton.disabled = !canAct;
    turnButton.addEventListener("click", runTurn);
    actionsBar.appendChild(turnButton);

    const inspectButton = document.createElement("button");
    inspectButton.textContent = "Inspect Selected";
    inspectButton.disabled =
      !canAct || !selectedSceneTargetSupportsAction(selectedSceneTarget, "inspect");
    inspectButton.addEventListener("click", () =>
      runSelectedSceneAction("inspect", "Inspect")
    );
    actionsBar.appendChild(inspectButton);

    const talkButton = document.createElement("button");
    talkButton.textContent = "Talk to Selected";
    talkButton.disabled =
      !canAct || !selectedSceneTargetSupportsAction(selectedSceneTarget, "talk");
    talkButton.addEventListener("click", () =>
      runSelectedSceneAction("talk", "Talk")
    );
    actionsBar.appendChild(talkButton);

    const useButton = document.createElement("button");
    useButton.textContent = "Use Selected";
    useButton.disabled =
      !canAct || !selectedSceneTargetSupportsAction(selectedSceneTarget, "use");
    useButton.addEventListener("click", () =>
      runSelectedSceneAction("use", "Use")
    );
    actionsBar.appendChild(useButton);

    const takeButton = document.createElement("button");
    takeButton.textContent = "Take Selected";
    takeButton.disabled =
      !canAct || !selectedSceneTargetSupportsAction(selectedSceneTarget, "take");
    takeButton.addEventListener("click", () =>
      runSelectedSceneAction("take", "Pickup")
    );
    actionsBar.appendChild(takeButton);

    mount.appendChild(actionsBar);

    const inventoryTitle = document.createElement("h3");
    inventoryTitle.textContent = "Inventory";
    mount.appendChild(inventoryTitle);

    if (!canAct) {
      const empty = document.createElement("div");
      empty.className = "note";
      empty.textContent = "Select an actor to act.";
      mount.appendChild(empty);
    } else if (!inventoryView.known) {
      const unknown = document.createElement("div");
      unknown.className = "note";
      unknown.textContent =
        "Inventory snapshot unavailable yet. It will appear after a successful turn response.";
      mount.appendChild(unknown);
    } else if (!inventoryView.items.length) {
      const none = document.createElement("div");
      none.className = "note";
      none.textContent = "No items in inventory.";
      mount.appendChild(none);
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

        itemButton.appendChild(itemHeader);
        itemButton.appendChild(itemDescription);
        inventoryList.appendChild(itemButton);
      }
      mount.appendChild(inventoryList);
    }

    restoreFocusState(mount, focusSnapshot);
  }

  render();
  store.subscribe(render);
}
