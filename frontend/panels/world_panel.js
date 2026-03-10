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

function formatWorldSummary(world) {
  const worldId =
    world && typeof world.world_id === "string" && world.world_id.trim()
      ? world.world_id.trim()
      : "unknown";
  const name =
    world && typeof world.name === "string" && world.name.trim()
      ? world.name.trim()
      : worldId;
  const generatorId =
    world?.generator && typeof world.generator.id === "string" && world.generator.id.trim()
      ? world.generator.id.trim()
      : "-";
  const updatedAt =
    world && typeof world.updated_at === "string" && world.updated_at.trim()
      ? world.updated_at.trim()
      : "-";
  return `${name} (${worldId}) | generator=${generatorId} | updated=${updatedAt}`;
}

export function initPanel(store) {
  const mount = document.getElementById("worldPanel");
  if (!mount) {
    return;
  }

  async function refreshWorldList() {
    const state = store.getState();
    const result = await store.refreshWorlds(state.baseUrl);
    if (!result.ok) {
      store.setStatusMessage(`Failed to load worlds (${result.status}).`);
      return;
    }
    const count = Array.isArray(result.data) ? result.data.length : 0;
    store.setStatusMessage(`Loaded ${count} world resource(s).`);
  }

  async function generateWorldEntry() {
    const state = store.getState();
    const result = await store.generateWorldResource(state.baseUrl);
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Generate world failed (${result.status}).`);
      return;
    }
    const suffix = result.data.created ? "created" : "normalized";
    store.setStatusMessage(`World ${result.data.world_id} ${suffix}.`);
  }

  function render() {
    const state = store.getState();
    const focusSnapshot = captureFocusState(mount);
    const worldState =
      state.worlds && typeof state.worlds === "object" ? state.worlds : {};
    const worlds = Array.isArray(worldState.list) ? worldState.list : [];
    const createForm =
      worldState.generate_form && typeof worldState.generate_form === "object"
        ? worldState.generate_form
        : {};
    const busy = worldState.status === "creating" || worldState.status === "loading";

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "World Resources";
    mount.appendChild(title);

    const topActions = document.createElement("div");
    topActions.className = "inline";
    const refreshButton = document.createElement("button");
    refreshButton.textContent = "Refresh Worlds";
    refreshButton.disabled = busy;
    refreshButton.addEventListener("click", refreshWorldList);
    topActions.appendChild(refreshButton);
    mount.appendChild(topActions);

    const status = document.createElement("div");
    status.className = "note";
    if (worldState.error) {
      status.textContent = `Error: ${worldState.error}`;
    } else if (worldState.status === "creating") {
      status.textContent = "Generating world resource...";
    } else if (worldState.status === "loading") {
      status.textContent = "Loading world resources...";
    } else if (worldState.last_generated_world_id) {
      status.textContent = `Last generated world: ${worldState.last_generated_world_id}`;
    } else {
      status.textContent = `World resources: ${worlds.length}`;
    }
    mount.appendChild(status);

    const list = document.createElement("div");
    list.className = "stack";
    if (!worlds.length) {
      const empty = document.createElement("div");
      empty.className = "row note";
      empty.textContent = "No world resources found yet. Default create flow still works.";
      list.appendChild(empty);
    } else {
      for (const world of worlds) {
        const row = document.createElement("div");
        row.className = "row";
        row.textContent = formatWorldSummary(world);
        list.appendChild(row);
      }
    }
    mount.appendChild(list);

    const createTitle = document.createElement("h3");
    createTitle.textContent = "Generate World";
    mount.appendChild(createTitle);

    const note = document.createElement("div");
    note.className = "note";
    note.textContent =
      "This creates or normalizes a world resource only. It does not bind any campaign.";
    mount.appendChild(note);

    const worldIdField = document.createElement("label");
    worldIdField.className = "field";
    worldIdField.innerHTML = '<span class="field-label">World ID</span>';
    const worldIdInput = document.createElement("input");
    worldIdInput.setAttribute("data-focus-key", "world-generate-id");
    worldIdInput.placeholder = "world_my_new_world";
    worldIdInput.value = createForm.world_id || "";
    worldIdInput.disabled = busy;
    worldIdInput.addEventListener("input", () => {
      store.setWorldGenerateForm({ world_id: worldIdInput.value });
    });
    worldIdField.appendChild(worldIdInput);
    mount.appendChild(worldIdField);

    const nameField = document.createElement("label");
    nameField.className = "field";
    nameField.innerHTML = '<span class="field-label">Name (optional)</span>';
    const nameInput = document.createElement("input");
    nameInput.setAttribute("data-focus-key", "world-generate-name");
    nameInput.placeholder = "Optional display name";
    nameInput.value = createForm.name || "";
    nameInput.disabled = busy;
    nameInput.addEventListener("input", () => {
      store.setWorldGenerateForm({ name: nameInput.value });
    });
    nameField.appendChild(nameInput);
    mount.appendChild(nameField);

    const generateButton = document.createElement("button");
    generateButton.className = "primary";
    generateButton.textContent = "Generate World";
    generateButton.disabled =
      busy || !(typeof createForm.world_id === "string" && createForm.world_id.trim());
    generateButton.addEventListener("click", generateWorldEntry);
    mount.appendChild(generateButton);

    restoreFocusState(mount, focusSnapshot);
  }

  render();
  store.subscribe(render);
  if (store.getState().backend?.ready !== false) {
    refreshWorldList();
  }
}
