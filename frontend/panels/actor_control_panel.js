import { chatTurn, getMapView } from "../api/api.js";

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

export function initPanel(store) {
  const mount = document.getElementById("actorControlPanel");
  if (!mount) {
    return;
  }

  const uiState = {
    actorId: "",
    userInput: "",
    moveToAreaId: "",
  };

  async function refreshMap(campaignId, actorId) {
    if (!campaignId || !actorId) {
      return;
    }
    const state = store.getState();
    const mapResult = await getMapView(state.baseUrl, campaignId, actorId);
    if (mapResult.ok && mapResult.data) {
      store.setMapView(mapResult.data);
    }
  }

  async function runTurn() {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    const actorId = uiState.actorId.trim();
    if (!actorId) {
      store.setStatusMessage("Select an actor.");
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
    const result = await chatTurn(state.baseUrl, payload);
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Turn failed: ${parseApiError(result)}`);
      store.setDebugResponseText(result.text || "");
      return;
    }
    if (result.data.state_summary) {
      store.setStateSummary(result.data.state_summary);
    }
    store.setDebugResponseText(JSON.stringify(result.data, null, 2));
    await refreshMap(state.campaignId, actorId);
    store.setStatusMessage("Turn completed.");
  }

  async function runMove() {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    const actorId = uiState.actorId.trim();
    const toAreaId = uiState.moveToAreaId.trim();
    if (!actorId || !toAreaId) {
      store.setStatusMessage("actor and to_area_id are required.");
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
    if (result.data.state_summary) {
      store.setStateSummary(result.data.state_summary);
    }
    store.setDebugResponseText(JSON.stringify(result.data, null, 2));
    await refreshMap(state.campaignId, actorId);
    store.setStatusMessage("Move completed.");
  }

  function render() {
    const state = store.getState();
    const party = Array.isArray(state.campaign?.party_character_ids)
      ? state.campaign.party_character_ids
      : Array.isArray(state.partyActors)
        ? state.partyActors
        : [];

    if (!uiState.actorId || !party.includes(uiState.actorId)) {
      uiState.actorId = party[0] || "";
    }

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Actor Control";
    mount.appendChild(title);

    const actorField = document.createElement("label");
    actorField.className = "field";
    actorField.innerHTML = '<span class="field-label">Actor</span>';
    const actorSelect = document.createElement("select");
    const actorEmpty = document.createElement("option");
    actorEmpty.value = "";
    actorEmpty.textContent = "Select actor";
    actorSelect.appendChild(actorEmpty);
    for (const actorId of party) {
      const option = document.createElement("option");
      option.value = actorId;
      option.textContent = actorId;
      option.selected = actorId === uiState.actorId;
      actorSelect.appendChild(option);
    }
    actorSelect.addEventListener("change", () => {
      uiState.actorId = actorSelect.value;
    });
    actorField.appendChild(actorSelect);
    mount.appendChild(actorField);

    const turnField = document.createElement("label");
    turnField.className = "field";
    turnField.innerHTML = '<span class="field-label">Turn Input</span>';
    const turnInput = document.createElement("textarea");
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
    turnButton.addEventListener("click", runTurn);
    mount.appendChild(turnButton);

    const moveField = document.createElement("label");
    moveField.className = "field";
    moveField.innerHTML = '<span class="field-label">Move to area_id</span>';
    const moveInput = document.createElement("input");
    moveInput.placeholder = "area_002";
    moveInput.value = uiState.moveToAreaId;
    moveInput.addEventListener("input", () => {
      uiState.moveToAreaId = moveInput.value;
    });
    moveField.appendChild(moveInput);
    mount.appendChild(moveField);

    const moveButton = document.createElement("button");
    moveButton.textContent = "Move";
    moveButton.addEventListener("click", runMove);
    mount.appendChild(moveButton);
  }

  render();
  store.subscribe(render);
}
