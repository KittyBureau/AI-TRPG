import {
  extractDebugResourcesFromResponseText,
  formatResourceEntry,
  RESOURCE_CATEGORIES,
} from "../utils/debug_resources.js";

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
