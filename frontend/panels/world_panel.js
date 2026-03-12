const SCENARIO_GENERATOR_ID = "playable_scenario_v0";

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

export function describeScenarioWorld(world) {
  const scenario =
    world && typeof world.scenario === "object" && !Array.isArray(world.scenario)
      ? world.scenario
      : null;
  if (!scenario) {
    return "";
  }
  const parts = ["scenario-backed"];
  if (typeof scenario.label === "string" && scenario.label.trim()) {
    parts.push(scenario.label.trim());
  } else if (typeof scenario.template_id === "string" && scenario.template_id.trim()) {
    parts.push(scenario.template_id.trim());
  }
  if (Number.isInteger(scenario.area_count)) {
    parts.push(`${scenario.area_count} areas`);
  }
  if (typeof scenario.difficulty === "string" && scenario.difficulty.trim()) {
    parts.push(scenario.difficulty.trim());
  }
  return parts.join(" | ");
}

export function formatWorldSummary(world) {
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
  const scenarioDescription = describeScenarioWorld(world);
  if (scenarioDescription) {
    return `${name} (${worldId}) | ${scenarioDescription} | updated=${updatedAt}`;
  }
  if (generatorId === SCENARIO_GENERATOR_ID) {
    return `${name} (${worldId}) | scenario-backed | updated=${updatedAt}`;
  }
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
    const scenarioMode = createForm.mode === "scenario";
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
    note.textContent = scenarioMode
      ? "Scenario mode stores normalized generator metadata only. Playable structure is rebuilt later during campaign bootstrap."
      : "This creates or normalizes a world resource only. It does not bind any campaign.";
    mount.appendChild(note);

    const modeField = document.createElement("label");
    modeField.className = "field";
    modeField.innerHTML = '<span class="field-label">Mode</span>';
    const modeSelect = document.createElement("select");
    modeSelect.setAttribute("data-focus-key", "world-generate-mode");
    modeSelect.disabled = busy;
    for (const option of [
      { value: "stub", label: "Normal / Stub" },
      { value: "scenario", label: "Scenario-backed" },
    ]) {
      const element = document.createElement("option");
      element.value = option.value;
      element.textContent = option.label;
      modeSelect.appendChild(element);
    }
    modeSelect.value = scenarioMode ? "scenario" : "stub";
    modeSelect.addEventListener("change", () => {
      store.setWorldGenerateForm({ mode: modeSelect.value });
    });
    modeField.appendChild(modeSelect);
    mount.appendChild(modeField);

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

    if (scenarioMode) {
      const templateField = document.createElement("label");
      templateField.className = "field";
      templateField.innerHTML = '<span class="field-label">Template</span>';
      const templateSelect = document.createElement("select");
      templateSelect.setAttribute("data-focus-key", "world-generate-scenario-template");
      templateSelect.disabled = busy;
      const templateOption = document.createElement("option");
      templateOption.value = "key_gate_scenario";
      templateOption.textContent = "Key Gate Scenario";
      templateSelect.appendChild(templateOption);
      templateSelect.value = createForm.scenario_template || "key_gate_scenario";
      templateSelect.addEventListener("change", () => {
        store.setWorldGenerateForm({ scenario_template: templateSelect.value });
      });
      templateField.appendChild(templateSelect);
      mount.appendChild(templateField);

      const themeField = document.createElement("label");
      themeField.className = "field";
      themeField.innerHTML = '<span class="field-label">Theme</span>';
      const themeInput = document.createElement("input");
      themeInput.setAttribute("data-focus-key", "world-generate-scenario-theme");
      themeInput.placeholder = "watchtower";
      themeInput.value = createForm.scenario_theme || "watchtower";
      themeInput.disabled = busy;
      themeInput.addEventListener("input", () => {
        store.setWorldGenerateForm({ scenario_theme: themeInput.value });
      });
      themeField.appendChild(themeInput);
      mount.appendChild(themeField);

      const areaCountField = document.createElement("label");
      areaCountField.className = "field";
      areaCountField.innerHTML = '<span class="field-label">Area Count</span>';
      const areaCountSelect = document.createElement("select");
      areaCountSelect.setAttribute("data-focus-key", "world-generate-scenario-area-count");
      areaCountSelect.disabled = busy;
      for (const areaCount of ["4", "5", "6", "7", "8"]) {
        const option = document.createElement("option");
        option.value = areaCount;
        option.textContent = areaCount;
        areaCountSelect.appendChild(option);
      }
      areaCountSelect.value = createForm.scenario_area_count || "6";
      areaCountSelect.addEventListener("change", () => {
        store.setWorldGenerateForm({ scenario_area_count: areaCountSelect.value });
      });
      areaCountField.appendChild(areaCountSelect);
      mount.appendChild(areaCountField);

      const layoutField = document.createElement("label");
      layoutField.className = "field";
      layoutField.innerHTML = '<span class="field-label">Layout</span>';
      const layoutSelect = document.createElement("select");
      layoutSelect.setAttribute("data-focus-key", "world-generate-scenario-layout");
      layoutSelect.disabled = busy;
      for (const option of [
        { value: "linear", label: "Linear" },
        { value: "branch", label: "Branch" },
      ]) {
        const element = document.createElement("option");
        element.value = option.value;
        element.textContent = option.label;
        layoutSelect.appendChild(element);
      }
      layoutSelect.value = createForm.scenario_layout_type || "branch";
      layoutSelect.addEventListener("change", () => {
        store.setWorldGenerateForm({ scenario_layout_type: layoutSelect.value });
      });
      layoutField.appendChild(layoutSelect);
      mount.appendChild(layoutField);

      const difficultyField = document.createElement("label");
      difficultyField.className = "field";
      difficultyField.innerHTML = '<span class="field-label">Difficulty</span>';
      const difficultySelect = document.createElement("select");
      difficultySelect.setAttribute("data-focus-key", "world-generate-scenario-difficulty");
      difficultySelect.disabled = busy;
      for (const option of [
        { value: "easy", label: "Easy" },
        { value: "standard", label: "Standard" },
      ]) {
        const element = document.createElement("option");
        element.value = option.value;
        element.textContent = option.label;
        difficultySelect.appendChild(element);
      }
      difficultySelect.value = createForm.scenario_difficulty || "easy";
      difficultySelect.addEventListener("change", () => {
        store.setWorldGenerateForm({ scenario_difficulty: difficultySelect.value });
      });
      difficultyField.appendChild(difficultySelect);
      mount.appendChild(difficultyField);
    }

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
