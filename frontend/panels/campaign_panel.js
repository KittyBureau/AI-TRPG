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
    createButton.addEventListener("click", createCampaignEntry);

    controls.appendChild(select);
    controls.appendChild(refreshButton);
    controls.appendChild(refreshCampaignButton);
    controls.appendChild(retryButton);
    controls.appendChild(createButton);
    campaignField.appendChild(controls);
    mount.appendChild(campaignField);

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
