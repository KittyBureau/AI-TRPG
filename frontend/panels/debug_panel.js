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

    const actions = document.createElement("div");
    actions.className = "inline";
    const clear = document.createElement("button");
    clear.textContent = "Clear Response";
    clear.addEventListener("click", () => {
      store.setDebugResponseText("");
    });
    actions.appendChild(clear);
    mount.appendChild(actions);

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
