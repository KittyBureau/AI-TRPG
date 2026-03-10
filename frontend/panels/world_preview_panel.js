function normalizeText(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

export function deriveWorldPreviewView(state) {
  const campaignId =
    typeof state?.campaignId === "string" && state.campaignId.trim()
      ? state.campaignId.trim()
      : "";
  const world =
    state?.campaign?.world && typeof state.campaign.world === "object"
      ? state.campaign.world
      : null;
  return {
    campaignId,
    hasWorld: Boolean(world && normalizeText(world.world_id)),
    world: world
      ? {
          world_id: normalizeText(world.world_id),
          name: normalizeText(world.name),
          world_description: normalizeText(world.world_description),
          objective: normalizeText(world.objective),
          start_area: normalizeText(world.start_area),
        }
      : null,
  };
}

function appendField(root, label, value) {
  const row = document.createElement("div");
  row.className = "row";
  row.textContent = `${label}: ${value || "-"}`;
  root.appendChild(row);
}

export function initPanel(store) {
  const mount = document.getElementById("worldPreviewPanel");
  if (!mount) {
    return;
  }

  let lastRequestKey = "";

  function maybeRefreshWorldPreview() {
    const state = store.getState();
    const baseUrl =
      typeof state.baseUrl === "string" && state.baseUrl.trim() ? state.baseUrl.trim() : "";
    const campaignId =
      typeof state.campaignId === "string" && state.campaignId.trim()
        ? state.campaignId.trim()
        : "";
    if (!campaignId) {
      lastRequestKey = "";
      return;
    }
    const requestKey = `${baseUrl}:${campaignId}`;
    if (requestKey === lastRequestKey) {
      return;
    }
    lastRequestKey = requestKey;
    void store.refreshCampaignWorldPreview(campaignId, state.baseUrl, { emit: true });
  }

  function render() {
    const view = deriveWorldPreviewView(store.getState());
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "World";
    mount.appendChild(title);

    if (!view.campaignId) {
      const empty = document.createElement("div");
      empty.className = "note";
      empty.textContent = "Select or create a campaign to load world context.";
      mount.appendChild(empty);
      return;
    }

    if (!view.hasWorld) {
      const missing = document.createElement("div");
      missing.className = "note";
      missing.textContent = "World preview unavailable for the current campaign.";
      mount.appendChild(missing);
      return;
    }

    appendField(mount, "World ID", view.world.world_id);
    appendField(mount, "Name", view.world.name || view.world.world_id);
    appendField(mount, "Description", view.world.world_description);
    appendField(mount, "Objective", view.world.objective);
    appendField(mount, "Start Area", view.world.start_area);
  }

  render();
  store.subscribe(() => {
    maybeRefreshWorldPreview();
    render();
  });
  maybeRefreshWorldPreview();
}
