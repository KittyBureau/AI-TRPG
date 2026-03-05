function toTagsInput(value) {
  if (!Array.isArray(value)) {
    return "";
  }
  return value.filter((item) => typeof item === "string" && item.trim()).join(", ");
}

export function initPanel(store) {
  const mount = document.getElementById("characterLibraryPanel");
  if (!mount) {
    return;
  }

  async function refreshLibrary() {
    const state = store.getState();
    const result = await store.loadCharacterLibrary(state.baseUrl);
    if (!result.ok) {
      store.setStatusMessage(`Failed to load character library (${result.status}).`);
      return;
    }
    const count = Array.isArray(result.data) ? result.data.length : 0;
    store.setStatusMessage(`Loaded ${count} character template(s).`);
  }

  async function createCharacter() {
    const state = store.getState();
    const result = await store.createCharacter(state.baseUrl);
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Create character failed (${result.status}).`);
      return;
    }
    await refreshLibrary();
    store.setStatusMessage(`Created character ${result.data.character_id}.`);
    store.setDebugResponseText(JSON.stringify(result.data, null, 2));
  }

  async function loadToCampaign(characterId) {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    const result = await store.loadCharacterToCampaign(
      state.campaignId,
      characterId,
      state.baseUrl
    );
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Load to campaign failed (${result.status}).`);
      return;
    }
    store.setStatusMessage("Character loaded to campaign.");
    store.setDebugResponseText(JSON.stringify(result.data, null, 2));
  }

  function render() {
    const state = store.getState();
    const library = Array.isArray(state.character?.library)
      ? state.character.library
      : [];
    const createForm = state.character?.create_form || {};

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Character Library";
    mount.appendChild(title);

    const topActions = document.createElement("div");
    topActions.className = "inline";
    const refreshButton = document.createElement("button");
    refreshButton.textContent = "Refresh";
    refreshButton.addEventListener("click", refreshLibrary);
    topActions.appendChild(refreshButton);
    mount.appendChild(topActions);

    const status = document.createElement("div");
    status.className = "note";
    if (state.character?.error) {
      status.textContent = `Error: ${state.character.error}`;
    } else {
      status.textContent = `Entries: ${library.length}`;
    }
    mount.appendChild(status);

    const list = document.createElement("div");
    list.className = "stack";
    if (!library.length) {
      const empty = document.createElement("div");
      empty.className = "row note";
      empty.textContent = "No character templates.";
      list.appendChild(empty);
    } else {
      for (const character of library) {
        const row = document.createElement("div");
        row.className = "row";

        const summary = document.createElement("div");
        const name = character?.name || character?.id || "Unnamed";
        const desc = character?.summary ? ` - ${character.summary}` : "";
        summary.textContent = `${name}${desc}`;
        row.appendChild(summary);

        const tags = document.createElement("div");
        tags.className = "note";
        tags.textContent = `id=${character.id} | tags=${toTagsInput(character.tags) || "-"}`;
        row.appendChild(tags);

        const actions = document.createElement("div");
        actions.className = "inline";
        const loadButton = document.createElement("button");
        loadButton.className = "primary";
        loadButton.textContent = "Load to Campaign";
        loadButton.addEventListener("click", () => loadToCampaign(character.id));
        actions.appendChild(loadButton);
        row.appendChild(actions);

        list.appendChild(row);
      }
    }
    mount.appendChild(list);

    const createTitle = document.createElement("h3");
    createTitle.textContent = "Create Character";
    mount.appendChild(createTitle);

    const nameField = document.createElement("label");
    nameField.className = "field";
    nameField.innerHTML = '<span class="field-label">Name</span>';
    const nameInput = document.createElement("input");
    nameInput.value = createForm.name || "";
    nameInput.addEventListener("input", () => {
      store.setCharacterCreateForm({ name: nameInput.value });
    });
    nameField.appendChild(nameInput);
    mount.appendChild(nameField);

    const summaryField = document.createElement("label");
    summaryField.className = "field";
    summaryField.innerHTML = '<span class="field-label">Summary</span>';
    const summaryInput = document.createElement("textarea");
    summaryInput.rows = 2;
    summaryInput.value = createForm.summary || "";
    summaryInput.addEventListener("input", () => {
      store.setCharacterCreateForm({ summary: summaryInput.value });
    });
    summaryField.appendChild(summaryInput);
    mount.appendChild(summaryField);

    const tagsField = document.createElement("label");
    tagsField.className = "field";
    tagsField.innerHTML = '<span class="field-label">Tags (comma separated)</span>';
    const tagsInput = document.createElement("input");
    tagsInput.value = createForm.tags || "";
    tagsInput.addEventListener("input", () => {
      store.setCharacterCreateForm({ tags: tagsInput.value });
    });
    tagsField.appendChild(tagsInput);
    mount.appendChild(tagsField);

    const createButton = document.createElement("button");
    createButton.className = "primary";
    createButton.textContent = "Create";
    createButton.addEventListener("click", createCharacter);
    mount.appendChild(createButton);
  }

  render();
  store.subscribe(render);
  refreshLibrary();
}
