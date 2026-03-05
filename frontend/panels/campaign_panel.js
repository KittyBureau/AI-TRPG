import { createCampaign, listCampaigns } from "../api/api.js";

export function initPanel(store) {
  const mount = document.getElementById("campaignPanel");
  if (!mount) {
    return;
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

  async function createCampaignEntry() {
    const state = store.getState();
    const result = await createCampaign(state.baseUrl, {});
    if (!result.ok || !result.data || !result.data.campaign_id) {
      store.setStatusMessage(`Create campaign failed (${result.status}).`);
      return;
    }
    await refreshCampaigns({ silent: true });
    store.setCampaignId(result.data.campaign_id);
    store.setPartyActors([]);
    store.setStatusMessage(`Created campaign ${result.data.campaign_id}.`);
    store.setDebugResponseText(JSON.stringify(result.data, null, 2));
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
    store.setStatusMessage(`Refreshed campaign ${state.campaignId} from backend authoritative state.`);
    if (result.data) {
      store.setDebugResponseText(JSON.stringify(result.data, null, 2));
    }
  }

  function changeCampaign(campaignId) {
    store.setCampaignId(campaignId);
    store.setPartyActors([]);
    store.setStatusMessage(
      campaignId ? `Selected campaign ${campaignId}.` : "Campaign cleared."
    );
  }

  function render() {
    const state = store.getState();
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Campaign";
    mount.appendChild(title);

    const baseField = document.createElement("label");
    baseField.className = "field";
    baseField.innerHTML = '<span class="field-label">Base URL</span>';
    const baseInput = document.createElement("input");
    baseInput.placeholder = "http://127.0.0.1:8000";
    baseInput.value = state.baseUrl || "";
    baseInput.addEventListener("change", () => {
      store.setBaseUrl(baseInput.value);
    });
    baseField.appendChild(baseInput);
    mount.appendChild(baseField);

    const campaignField = document.createElement("label");
    campaignField.className = "field";
    campaignField.innerHTML = '<span class="field-label">Current Campaign</span>';
    const controls = document.createElement("div");
    controls.className = "inline";

    const select = document.createElement("select");
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
    select.addEventListener("change", () => changeCampaign(select.value));

    const refreshButton = document.createElement("button");
    refreshButton.textContent = "Refresh";
    refreshButton.addEventListener("click", () => refreshCampaigns());

    const refreshCampaignButton = document.createElement("button");
    refreshCampaignButton.textContent = "Refresh Campaign";
    refreshCampaignButton.addEventListener("click", refreshCurrentCampaign);

    const createButton = document.createElement("button");
    createButton.className = "primary";
    createButton.textContent = "Create Campaign";
    createButton.addEventListener("click", createCampaignEntry);

    controls.appendChild(select);
    controls.appendChild(refreshButton);
    controls.appendChild(refreshCampaignButton);
    controls.appendChild(createButton);
    campaignField.appendChild(controls);
    mount.appendChild(campaignField);
  }

  render();
  store.subscribe(render);
  refreshCampaigns({ silent: true });
}
