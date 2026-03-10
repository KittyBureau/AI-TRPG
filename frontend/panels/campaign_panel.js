import { createCampaign, listCampaigns } from "../api/api.js";

export function formatCampaignStatusLines(status) {
  if (!status || typeof status !== "object") {
    return ["Campaign status unavailable until authoritative refresh succeeds."];
  }
  const milestone =
    status.milestone && typeof status.milestone === "object" ? status.milestone : null;
  const milestoneCurrent =
    typeof milestone?.current === "string" && milestone.current.trim()
      ? milestone.current.trim()
      : "";
  if (!milestoneCurrent) {
    return ["Campaign status unavailable until authoritative refresh succeeds."];
  }

  const lines = [`Status: ${status.ended === true ? "ended" : "active"}`];
  lines.push(`Milestone: ${milestoneCurrent}`);
  if (typeof milestone.summary === "string" && milestone.summary.trim()) {
    lines.push(`Milestone summary: ${milestone.summary.trim()}`);
  }
  if (status.ended === true && typeof status.reason === "string" && status.reason.trim()) {
    lines.push(`Ended reason: ${status.reason.trim()}`);
  }
  return lines;
}

export function initPanel(store) {
  const mount = document.getElementById("campaignPanel");
  if (!mount) {
    return;
  }
  const uiState = {
    selectedCharacterIds: [],
    requestedActiveActorId: "",
    selectedWorldId: "",
    submitting: false,
  };

  function getOrderedSelectedCharacterIds(library) {
    const selected = new Set(uiState.selectedCharacterIds);
    return library
      .map((character) =>
        character && typeof character.id === "string" ? character.id.trim() : ""
      )
      .filter((characterId) => characterId && selected.has(characterId));
  }

  function syncSelectedPartyState(library) {
    const orderedIds = getOrderedSelectedCharacterIds(library);
    uiState.selectedCharacterIds = orderedIds;
    if (!orderedIds.length) {
      uiState.requestedActiveActorId = "";
      return orderedIds;
    }
    if (!orderedIds.includes(uiState.requestedActiveActorId)) {
      uiState.requestedActiveActorId = orderedIds[0];
    }
    return orderedIds;
  }

  async function refreshCampaigns({ silent = false } = {}) {
    const state = store.getState();
    const result = await listCampaigns(state.baseUrl);
    if (!result.ok || !result.data || !Array.isArray(result.data.campaigns)) {
      if (!silent) {
        store.setStatusMessage(`Failed to load campaigns (${result.status}).`);
      }
      return;
    }
    store.setCampaignOptions(result.data.campaigns);
    if (!silent) {
      store.setStatusMessage(`Loaded ${result.data.campaigns.length} campaigns.`);
    }
  }

  async function refreshWorlds({ silent = false } = {}) {
    const state = store.getState();
    const result = await store.refreshWorlds(state.baseUrl, { emit: silent !== true });
    if (!result.ok || !Array.isArray(result.data)) {
      if (!silent) {
        store.setStatusMessage(`Failed to load worlds (${result.status}).`);
      }
      return result;
    }
    if (
      uiState.selectedWorldId &&
      !result.data.some((world) => world && world.world_id === uiState.selectedWorldId)
    ) {
      uiState.selectedWorldId = "";
    }
    if (!silent) {
      store.setStatusMessage(`Loaded ${result.data.length} world(s).`);
    }
    return result;
  }

  async function createCampaignEntry() {
    if (uiState.submitting) {
      return;
    }
    uiState.submitting = true;
    render();
    const state = store.getState();
    const result = await createCampaign(state.baseUrl, {});
    try {
      if (!result.ok || !result.data || !result.data.campaign_id) {
        store.setStatusMessage(`Create campaign failed (${result.status}).`);
        return;
      }
      await refreshCampaigns({ silent: true });
      store.setCampaignId(result.data.campaign_id);
      const refreshResult = await store.refreshCampaign(result.data.campaign_id, state.baseUrl);
      if (!refreshResult.ok) {
        store.setPartyActors([]);
        store.setStatusMessage(
          `Created campaign ${result.data.campaign_id}, but refresh failed (${refreshResult.status}).`
        );
        return;
      }
      store.setStatusMessage(`Created campaign ${result.data.campaign_id}.`);
      store.setDebugResponseText(JSON.stringify(result.data, null, 2));
    } finally {
      uiState.submitting = false;
      render();
    }
  }

  async function createCampaignWithSelectedPartyEntry() {
    if (uiState.submitting) {
      return;
    }
    const state = store.getState();
    const library = Array.isArray(state.character?.library) ? state.character.library : [];
    const selectedCharacterIds = syncSelectedPartyState(library);
    if (!selectedCharacterIds.length) {
      store.setStatusMessage("Select at least one character for explicit party create.");
      render();
      return;
    }
    uiState.submitting = true;
    render();
    try {
      const result = await store.createCampaignWithSelectedParty(
        {
          characterIds: selectedCharacterIds,
          activeActorId: uiState.requestedActiveActorId || selectedCharacterIds[0],
          worldId: uiState.selectedWorldId,
        },
        state.baseUrl
      );
      if (!result.ok || !result.data || !result.data.campaign_id) {
        store.setStatusMessage(`Create campaign failed (${result.status}).`);
        return;
      }
      await refreshCampaigns({ silent: true });
      store.setCampaignId(result.data.campaign_id);
      store.setDebugResponseText(JSON.stringify(result.data, null, 2));
    } finally {
      uiState.submitting = false;
      render();
    }
  }

  async function refreshCurrentCampaign() {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    const result = await store.refreshCampaign(state.campaignId, state.baseUrl);
    if (!result.ok) {
      store.setStatusMessage(`Refresh campaign failed (${result.status}).`);
      return;
    }
    if (typeof store.refreshCampaignWorldPreview === "function") {
      await store.refreshCampaignWorldPreview(state.campaignId, state.baseUrl, { emit: true });
    }
    store.setStatusMessage(`Refreshed campaign ${state.campaignId} from backend authoritative state.`);
    if (result.data) {
      store.setDebugResponseText(JSON.stringify(result.data, null, 2));
    }
  }

  async function changeCampaign(campaignId) {
    store.setCampaignId(campaignId);
    if (!campaignId) {
      store.setPartyActors([]);
      store.setStatusMessage("Campaign cleared.");
      return;
    }
    const result = await store.refreshCampaign(campaignId, store.getState().baseUrl);
    if (!result.ok) {
      store.setPartyActors([]);
      store.setStatusMessage(`Selected campaign ${campaignId}, but refresh failed (${result.status}).`);
      return;
    }
    if (typeof store.refreshCampaignWorldPreview === "function") {
      await store.refreshCampaignWorldPreview(campaignId, store.getState().baseUrl, { emit: true });
    }
    if (result.data) {
      store.setDebugResponseText(JSON.stringify(result.data, null, 2));
    }
    store.setStatusMessage(`Selected campaign ${campaignId}.`);
  }

  function captureFocusState() {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement) || !mount.contains(active)) {
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

  function restoreFocusState(snapshot) {
    if (!snapshot) {
      return;
    }
    const target = mount.querySelector(`[data-focus-key="${snapshot.key}"]`);
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

  function render() {
    const state = store.getState();
    const focusSnapshot = captureFocusState();
    const library = Array.isArray(state.character?.library) ? state.character.library : [];
    const orderedSelectedCharacterIds = syncSelectedPartyState(library);
    const worlds = Array.isArray(state.worlds?.list) ? state.worlds.list : [];
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Campaign";
    mount.appendChild(title);

    const baseField = document.createElement("label");
    baseField.className = "field";
    baseField.innerHTML = '<span class="field-label">Base URL</span>';
    const baseInput = document.createElement("input");
    baseInput.setAttribute("data-focus-key", "base-url-input");
    baseInput.placeholder = "http://127.0.0.1:8000";
    baseInput.value = state.baseUrl || "";
    baseInput.addEventListener("change", async () => {
      store.setBaseUrl(baseInput.value);
      if (typeof store.recoverRuntime === "function" && store.getState().baseUrl) {
        await store.recoverRuntime({ silent: false, manual: true });
      }
      await refreshWorlds({ silent: true });
    });
    baseField.appendChild(baseInput);
    mount.appendChild(baseField);

    const campaignField = document.createElement("label");
    campaignField.className = "field";
    campaignField.innerHTML = '<span class="field-label">Current Campaign</span>';
    const controls = document.createElement("div");
    controls.className = "inline";

    const select = document.createElement("select");
    select.setAttribute("data-focus-key", "campaign-select");
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Select campaign";
    select.appendChild(empty);
    for (const campaign of state.campaignOptions || []) {
      const option = document.createElement("option");
      option.value = campaign.id;
      option.textContent = `${campaign.id} (active=${campaign.active_actor_id})`;
      option.selected = campaign.id === state.campaignId;
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      void changeCampaign(select.value);
    });

    const refreshButton = document.createElement("button");
    refreshButton.textContent = "Refresh";
    refreshButton.addEventListener("click", () => refreshCampaigns());

    const refreshCampaignButton = document.createElement("button");
    refreshCampaignButton.textContent = "Refresh Campaign";
    refreshCampaignButton.addEventListener("click", refreshCurrentCampaign);

    const retryButton = document.createElement("button");
    retryButton.textContent = "Retry Connection";
    retryButton.addEventListener("click", async () => {
      if (typeof store.recoverRuntime === "function") {
        const recovered = await store.recoverRuntime({ silent: false, manual: true });
        if (!recovered && store.getState().backend?.ready !== false) {
          await refreshCampaigns();
        }
      } else {
        await refreshCampaigns();
      }
    });

    const createButton = document.createElement("button");
    createButton.className = "primary";
    createButton.textContent = "Create Campaign";
    createButton.disabled = uiState.submitting;
    createButton.addEventListener("click", createCampaignEntry);

    const createWithPartyButton = document.createElement("button");
    createWithPartyButton.textContent = "Create With Selected Party";
    createWithPartyButton.disabled = uiState.submitting || !orderedSelectedCharacterIds.length;
    createWithPartyButton.addEventListener("click", createCampaignWithSelectedPartyEntry);

    controls.appendChild(select);
    controls.appendChild(refreshButton);
    controls.appendChild(refreshCampaignButton);
    controls.appendChild(retryButton);
    controls.appendChild(createButton);
    controls.appendChild(createWithPartyButton);
    campaignField.appendChild(controls);
    mount.appendChild(campaignField);

    const explicitPartyTitle = document.createElement("h3");
    explicitPartyTitle.textContent = "Explicit Party Create";
    mount.appendChild(explicitPartyTitle);

    const explicitPartyNote = document.createElement("div");
    explicitPartyNote.className = "note";
    explicitPartyNote.textContent =
      "Selected library characters are created as the initial party, then loaded through the existing party/load chain to hydrate adopted profiles.";
    mount.appendChild(explicitPartyNote);

    const worldField = document.createElement("label");
    worldField.className = "field";
    worldField.innerHTML = '<span class="field-label">Existing World (optional)</span>';
    const worldControls = document.createElement("div");
    worldControls.className = "inline";
    const worldSelect = document.createElement("select");
    worldSelect.setAttribute("data-focus-key", "explicit-create-world");
    const worldEmptyOption = document.createElement("option");
    worldEmptyOption.value = "";
    worldEmptyOption.textContent = "Default campaign world";
    worldSelect.appendChild(worldEmptyOption);
    for (const world of worlds) {
      const worldId =
        world && typeof world.world_id === "string" ? world.world_id.trim() : "";
      if (!worldId) {
        continue;
      }
      const option = document.createElement("option");
      option.value = worldId;
      const name =
        world && typeof world.name === "string" && world.name.trim()
          ? world.name.trim()
          : worldId;
      const generatorId =
        world?.generator && typeof world.generator.id === "string" && world.generator.id.trim()
          ? world.generator.id.trim()
          : "";
      option.textContent = generatorId ? `${name} (${worldId}, ${generatorId})` : `${name} (${worldId})`;
      option.selected = worldId === uiState.selectedWorldId;
      worldSelect.appendChild(option);
    }
    worldSelect.disabled = uiState.submitting;
    worldSelect.addEventListener("change", () => {
      uiState.selectedWorldId = worldSelect.value.trim();
      render();
    });
    const worldRefreshButton = document.createElement("button");
    worldRefreshButton.type = "button";
    worldRefreshButton.textContent = "Refresh Worlds";
    worldRefreshButton.disabled = uiState.submitting;
    worldRefreshButton.addEventListener("click", () => {
      void refreshWorlds();
    });
    worldControls.appendChild(worldSelect);
    worldControls.appendChild(worldRefreshButton);
    worldField.appendChild(worldControls);
    mount.appendChild(worldField);

    const worldNote = document.createElement("div");
    worldNote.className = "note";
    worldNote.textContent = worlds.length
      ? "Optional world binding for explicit create. Leave empty to keep the old default world path."
      : "No saved worlds found. Explicit create can still use the old default world path.";
    mount.appendChild(worldNote);

    const partySelectionList = document.createElement("div");
    partySelectionList.className = "stack";
    if (!library.length) {
      const emptyLibrary = document.createElement("div");
      emptyLibrary.className = "note";
      emptyLibrary.textContent =
        "No character library entries available yet. Use the default create path or create/load characters first.";
      partySelectionList.appendChild(emptyLibrary);
    } else {
      for (const character of library) {
        const characterId =
          character && typeof character.id === "string" ? character.id.trim() : "";
        if (!characterId) {
          continue;
        }
        const label = document.createElement("label");
        label.className = "row";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = orderedSelectedCharacterIds.includes(characterId);
        checkbox.addEventListener("change", () => {
          const nextSelected = new Set(uiState.selectedCharacterIds);
          if (checkbox.checked) {
            nextSelected.add(characterId);
          } else {
            nextSelected.delete(characterId);
          }
          uiState.selectedCharacterIds = [...nextSelected];
          syncSelectedPartyState(
            Array.isArray(store.getState().character?.library)
              ? store.getState().character.library
              : []
          );
          render();
        });
        label.appendChild(checkbox);

        const text = document.createElement("span");
        const name =
          character && typeof character.name === "string" && character.name.trim()
            ? character.name.trim()
            : characterId;
        const summary =
          character && typeof character.summary === "string" && character.summary.trim()
            ? ` - ${character.summary.trim()}`
            : "";
        text.textContent = `${name} (${characterId})${summary}`;
        label.appendChild(text);
        partySelectionList.appendChild(label);
      }
    }
    mount.appendChild(partySelectionList);

    const activeActorField = document.createElement("label");
    activeActorField.className = "field";
    activeActorField.innerHTML = '<span class="field-label">Explicit Active Actor</span>';
    const activeActorSelect = document.createElement("select");
    activeActorSelect.setAttribute("data-focus-key", "explicit-create-active-actor");
    const emptyActorOption = document.createElement("option");
    emptyActorOption.value = "";
    emptyActorOption.textContent = "First selected character";
    activeActorSelect.appendChild(emptyActorOption);
    for (const characterId of orderedSelectedCharacterIds) {
      const option = document.createElement("option");
      option.value = characterId;
      option.textContent = characterId;
      option.selected = characterId === uiState.requestedActiveActorId;
      activeActorSelect.appendChild(option);
    }
    activeActorSelect.disabled = !orderedSelectedCharacterIds.length || uiState.submitting;
    activeActorSelect.addEventListener("change", () => {
      uiState.requestedActiveActorId = activeActorSelect.value.trim();
      render();
    });
    activeActorField.appendChild(activeActorSelect);
    mount.appendChild(activeActorField);

    const statusBlock = document.createElement("div");
    statusBlock.className = "note";
    for (const line of formatCampaignStatusLines(state.campaign?.status)) {
      const row = document.createElement("div");
      row.textContent = line;
      statusBlock.appendChild(row);
    }
    mount.appendChild(statusBlock);

    if (state.backend?.ready === false) {
      const note = document.createElement("div");
      note.className = "note";
      note.textContent =
        "Backend not ready. Run `python -m backend.tools.unlock_keyring`, then click Retry Connection.";
      mount.appendChild(note);
    }

    restoreFocusState(focusSnapshot);
  }

  render();
  store.subscribe(render);
  if (store.getState().backend?.ready !== false) {
    refreshCampaigns({ silent: true });
  }
}
