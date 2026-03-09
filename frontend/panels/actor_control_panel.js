import { chatTurn, getMapView } from "../api/api.js";
import { getPartyActorIds, resolveActingActorId } from "../utils/acting_actor.js";

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

function getActorInventoryView(state, actorId) {
  const inventoryByActor =
    state?.inventoryByActor && typeof state.inventoryByActor === "object"
      ? state.inventoryByActor
      : {};
  if (!actorId || !hasOwn(inventoryByActor, actorId)) {
    return {
      known: false,
      entries: [],
    };
  }
  const inventory =
    inventoryByActor[actorId] && typeof inventoryByActor[actorId] === "object"
      ? inventoryByActor[actorId]
      : {};
  return {
    known: true,
    entries: Object.entries(inventory).sort(([left], [right]) => left.localeCompare(right)),
  };
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
  let lastMapRequestKey = "";

  async function refreshMap(campaignId, actorId, options = {}) {
    if (!campaignId || !actorId) {
      if (options.clearWhenMissing === true) {
        store.setMapView(null);
      }
      return;
    }
    const requestKey = `${campaignId}:${actorId}`;
    lastMapRequestKey = requestKey;
    const state = store.getState();
    const mapResult = await getMapView(state.baseUrl, campaignId, actorId);
    const nextState = store.getState();
    const nextActorId = resolveActingActorId(nextState);
    const nextRequestKey =
      nextState.campaignId && nextActorId ? `${nextState.campaignId}:${nextActorId}` : "";
    if (requestKey !== lastMapRequestKey || nextRequestKey !== requestKey) {
      return;
    }
    if (mapResult.ok && mapResult.data) {
      store.setMapView(mapResult.data);
      return;
    }
    if (options.clearOnFailure === true) {
      store.setMapView(null);
    }
  }

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
    const payload = {
      campaign_id: state.campaignId,
      user_input: userInput,
      execution: { actor_id: actorId },
    };
    const selectedItemId =
      state.selectedItemIdByActor && typeof state.selectedItemIdByActor === "object"
        ? state.selectedItemIdByActor[actorId]
        : null;
    if (typeof selectedItemId === "string" && selectedItemId.trim()) {
      payload.context_hints = {
        selected_item_id: selectedItemId.trim(),
      };
    }
    const result = await chatTurn(state.baseUrl, payload);
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Turn failed: ${parseApiError(result)}`);
      store.setDebugResponseText(result.text || "");
      return;
    }
    store.recordTurnResult(result.data, JSON.stringify(result.data, null, 2));
    await refreshMap(state.campaignId, actorId);
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
    await refreshMap(state.campaignId, actorId);
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
    const inventoryView = getActorInventoryView(state, actingActorId);
    const selectedItemId =
      actingActorId && state.selectedItemIdByActor
        ? state.selectedItemIdByActor[actingActorId] || null
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
    selectionRow.textContent = `Selected item: ${selectedItemId || "none"}`;
    mount.appendChild(selectionRow);

    const inventoryNote = document.createElement("div");
    inventoryNote.className = "note";
    inventoryNote.textContent =
      "Selection is stored per actor in the frontend and sent as an optional selected-item hint on turn requests.";
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
    } else if (!inventoryView.entries.length) {
      const inventoryNone = document.createElement("div");
      inventoryNone.className = "note";
      inventoryNone.textContent = "No items in inventory.";
      mount.appendChild(inventoryNone);
    } else {
      const inventoryList = document.createElement("div");
      inventoryList.className = "stack";
      for (const [itemId, quantity] of inventoryView.entries) {
        const itemButton = document.createElement("button");
        itemButton.type = "button";
        itemButton.className =
        itemId === selectedItemId ? "inventory-item selected" : "inventory-item";
        itemButton.textContent = `${itemId} x${quantity}`;
        itemButton.addEventListener("click", () => {
          const selected = store.setSelectedItemForActor(actingActorId, itemId);
          if (!selected) {
            store.setStatusMessage(`Failed to select item: ${itemId}`);
          }
        });
        inventoryList.appendChild(itemButton);
      }
      mount.appendChild(inventoryList);
    }

    const mapTitle = document.createElement("h3");
    mapTitle.textContent = "Map Snapshot";
    mount.appendChild(mapTitle);

    const mapView =
      state.mapView && typeof state.mapView === "object" ? state.mapView : null;
    if (!canAct) {
      const mapEmpty = document.createElement("div");
      mapEmpty.className = "note";
      mapEmpty.textContent = "Select an actor to inspect map context.";
      mount.appendChild(mapEmpty);
    } else if (!mapView || mapView.active_actor_id !== actingActorId) {
      const mapLoading = document.createElement("div");
      mapLoading.className = "note";
      mapLoading.textContent = "Map snapshot unavailable yet.";
      mount.appendChild(mapLoading);
    } else {
      const actorRow = document.createElement("div");
      actorRow.className = "note";
      actorRow.textContent = `Active actor: ${mapView.active_actor_id}`;
      mount.appendChild(actorRow);

      const currentArea = mapView.current_area || {};
      const areaRow = document.createElement("div");
      areaRow.className = "note";
      areaRow.textContent = `Current area: ${currentArea.name || "-"} (${currentArea.id || "-"})`;
      mount.appendChild(areaRow);

      const reachableTitle = document.createElement("div");
      reachableTitle.className = "note";
      reachableTitle.textContent = `Reachable areas (${Array.isArray(mapView.reachable_areas) ? mapView.reachable_areas.length : 0})`;
      mount.appendChild(reachableTitle);

      const reachableList = document.createElement("div");
      reachableList.className = "stack";
      const reachableAreas = Array.isArray(mapView.reachable_areas) ? mapView.reachable_areas : [];
      if (!reachableAreas.length) {
        const none = document.createElement("div");
        none.className = "row note";
        none.textContent = "(none)";
        reachableList.appendChild(none);
      } else {
        for (const area of reachableAreas) {
          const row = document.createElement("div");
          row.className = "row";
          row.textContent = `${area.name || "-"} (${area.id || "-"})`;
          reachableList.appendChild(row);
        }
      }
      mount.appendChild(reachableList);
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
  let lastObservedMapKey = "";
  store.subscribe(() => {
    const state = store.getState();
    const actorId = resolveActingActorId(state);
    const nextMapKey =
      state.campaignId && actorId ? `${state.campaignId}:${actorId}` : "";
    if (nextMapKey !== lastObservedMapKey) {
      lastObservedMapKey = nextMapKey;
      void refreshMap(state.campaignId, actorId, {
        clearWhenMissing: true,
        clearOnFailure: true,
      });
    }
    render();
  });
  const initialState = store.getState();
  const initialActorId = resolveActingActorId(initialState);
  if (initialState.campaignId && initialActorId) {
    lastObservedMapKey = `${initialState.campaignId}:${initialActorId}`;
    void refreshMap(initialState.campaignId, initialActorId, {
      clearOnFailure: true,
    });
  }
}
