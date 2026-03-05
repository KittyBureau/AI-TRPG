export function initPanel(store) {
  const mount = document.getElementById("partyPanel");
  if (!mount) {
    return;
  }
  const uiState = {
    selectedActorId: "",
    statusText: "",
    errorText: "",
  };

  function parseApiError(result) {
    if (result?.data && typeof result.data.detail === "string") {
      return result.data.detail;
    }
    if (typeof result?.text === "string" && result.text.trim()) {
      return result.text.trim();
    }
    return `HTTP ${result?.status ?? 500}`;
  }

  async function setActiveActor() {
    const actorId = (uiState.selectedActorId || "").trim();
    if (!actorId) {
      uiState.statusText = "";
      uiState.errorText = "Select an actor first.";
      render();
      return;
    }
    const result = await store.selectActiveActor(actorId);
    if (!result.ok) {
      const message = parseApiError(result);
      uiState.statusText = "";
      uiState.errorText = `Set active failed: ${message}`;
      console.error("Set active actor failed", result);
      render();
      return;
    }
    uiState.errorText = "";
    uiState.statusText = `Active actor set to ${actorId}.`;
    render();
  }

  function render() {
    const state = store.getState();
    const party = Array.isArray(state.campaign?.party_character_ids)
      ? state.campaign.party_character_ids
      : Array.isArray(state.partyActors)
        ? state.partyActors
        : [];
    const activeActorId = state.campaign?.active_actor_id || "";
    if (!uiState.selectedActorId || !party.includes(uiState.selectedActorId)) {
      uiState.selectedActorId = activeActorId && party.includes(activeActorId)
        ? activeActorId
        : party[0] || "";
    }

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Party";
    mount.appendChild(title);

    const active = document.createElement("div");
    active.className = "row";
    active.textContent = `active_actor_id: ${activeActorId || "none"}`;
    mount.appendChild(active);

    const controls = document.createElement("label");
    controls.className = "field";
    controls.innerHTML = '<span class="field-label">Set active actor</span>';
    const controlsRow = document.createElement("div");
    controlsRow.className = "inline";

    const select = document.createElement("select");
    const emptyOption = document.createElement("option");
    emptyOption.value = "";
    emptyOption.textContent = "Select actor";
    select.appendChild(emptyOption);
    for (const actorId of party) {
      const option = document.createElement("option");
      option.value = actorId;
      option.textContent = actorId;
      option.selected = actorId === uiState.selectedActorId;
      select.appendChild(option);
    }
    select.addEventListener("change", () => {
      uiState.selectedActorId = select.value;
    });

    const setButton = document.createElement("button");
    setButton.className = "primary";
    setButton.textContent = "Set Active";
    setButton.disabled = !party.length;
    setButton.addEventListener("click", setActiveActor);

    controlsRow.appendChild(select);
    controlsRow.appendChild(setButton);
    controls.appendChild(controlsRow);
    mount.appendChild(controls);

    const status = document.createElement("div");
    status.className = "note";
    status.textContent =
      uiState.errorText || uiState.statusText || "Use party actors to switch active actor.";
    mount.appendChild(status);

    const listTitle = document.createElement("div");
    listTitle.className = "note";
    listTitle.textContent = "party_character_ids";
    mount.appendChild(listTitle);

    const list = document.createElement("div");
    list.className = "stack";
    if (!party.length) {
      const empty = document.createElement("div");
      empty.className = "row note";
      empty.textContent = "No party actors.";
      list.appendChild(empty);
    } else {
      for (const actorId of party) {
        const row = document.createElement("div");
        row.className = "row";
        row.textContent = actorId;
        list.appendChild(row);
      }
    }
    mount.appendChild(list);
  }

  render();
  store.subscribe(render);
}
