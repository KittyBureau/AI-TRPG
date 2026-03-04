const panelRegistry = [];

export function registerPanel(panel) {
  if (!panel || typeof panel !== "object") {
    throw new Error("panel definition is required");
  }
  const requiredFields = ["id", "title", "group", "mount", "render"];
  for (const key of requiredFields) {
    if (!(key in panel)) {
      throw new Error(`panel missing field: ${key}`);
    }
  }
  panelRegistry.push(panel);
}

export function clearPanelRegistry() {
  panelRegistry.length = 0;
}

function createPanelContainer(title) {
  const panel = document.createElement("section");
  panel.className = "panel";

  const header = document.createElement("div");
  header.className = "panel-header";
  header.textContent = title;

  const body = document.createElement("div");
  body.className = "panel-body";

  panel.appendChild(header);
  panel.appendChild(body);
  return { panel, body };
}

export function renderPanels({ mounts, state, context }) {
  const mountEntries = Object.entries(mounts || {});
  for (const [, mountElement] of mountEntries) {
    if (mountElement) {
      mountElement.innerHTML = "";
    }
  }

  for (const panelDefinition of panelRegistry) {
    const mountElement = mounts?.[panelDefinition.mount];
    if (!mountElement) {
      continue;
    }
    const { panel, body } = createPanelContainer(panelDefinition.title);
    panel.setAttribute("data-panel-id", panelDefinition.id);
    panel.setAttribute("data-panel-group", panelDefinition.group);
    panelDefinition.render(body, state, context);
    mountElement.appendChild(panel);
  }
}
