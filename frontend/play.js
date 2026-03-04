import { createCampaign, getMapView, listCampaigns } from "./api/api.js";
import {
  addPlannedAction,
  getState,
  initializeStore,
  setBaseUrl,
  setCampaignId,
  setCampaignOptions,
  setMapView,
  setPartyActors,
  setStatusMessage,
  subscribe,
} from "./store/store.js";
import { clearPanelRegistry, registerPanel, renderPanels } from "./panels/registry.js";
import { renderActionPlannerPanel } from "./panels/action_planner.js";
import { renderLogPanel } from "./panels/log_panel.js";
import { renderCampaignPanel, renderPartyPanel } from "./panels/party_panel.js";
import { renderMapPlaceholderPanel, renderScenePanel } from "./panels/scene_panel.js";

const statusLine = document.getElementById("statusLine");

function setStatus(text) {
  setStatusMessage(text);
}

function renderStatusLine() {
  if (statusLine) {
    statusLine.textContent = getState().statusMessage || "Idle";
  }
}

async function refreshMapView(campaignId, actorId = null) {
  const state = getState();
  if (!campaignId) {
    setMapView(null);
    return;
  }
  const result = await getMapView(state.baseUrl, campaignId, actorId);
  if (result.ok && result.data) {
    setMapView(result.data);
  }
}

async function refreshCampaigns() {
  const state = getState();
  const result = await listCampaigns(state.baseUrl);
  if (!result.ok || !result.data || !Array.isArray(result.data.campaigns)) {
    setStatus(`Failed to load campaigns (${result.status}).`);
    return;
  }

  const campaigns = result.data.campaigns;
  setCampaignOptions(campaigns);

  const latestState = getState();
  if (latestState.campaignId) {
    await refreshMapView(latestState.campaignId);
  }
  setStatus(`Loaded ${campaigns.length} campaigns.`);
}

async function createCampaignAndRefresh() {
  const state = getState();
  const result = await createCampaign(state.baseUrl, {});
  if (!result.ok || !result.data || !result.data.campaign_id) {
    setStatus(`Create campaign failed (${result.status}).`);
    return;
  }
  setCampaignId(result.data.campaign_id);
  await refreshCampaigns();
  await refreshMapView(result.data.campaign_id);
  setStatus(`Created campaign ${result.data.campaign_id}.`);
}

async function changeCampaign(campaignId) {
  setCampaignId(campaignId);
  await refreshMapView(campaignId);
}

function setPartyFromSummary() {
  const summary = getState().stateSummary;
  const actorIds = summary?.positions && typeof summary.positions === "object"
    ? Object.keys(summary.positions).sort()
    : [];
  setPartyActors(actorIds);
  setStatus(`Party set from summary (${actorIds.length} actors).`);
}

function addSceneAction(envelope) {
  const ok = addPlannedAction(envelope);
  if (!ok) {
    setStatus("Failed to add scene action.");
    return;
  }
  const action = envelope?.action || "scene_action";
  const target = envelope?.target_label || envelope?.target_id || "";
  setStatus(`Queued ${action} -> ${target}`.trim());
}

function registerPlayPanels() {
  clearPanelRegistry();
  registerPanel({
    id: "campaign",
    title: "Campaign Bar",
    group: "campaign",
    mount: "campaign",
    render: renderCampaignPanel,
  });
  registerPanel({
    id: "party",
    title: "Party",
    group: "party",
    mount: "left",
    render: renderPartyPanel,
  });
  registerPanel({
    id: "planner",
    title: "Action Planner",
    group: "action",
    mount: "left",
    render: renderActionPlannerPanel,
  });
  registerPanel({
    id: "scene",
    title: "Scene",
    group: "scene",
    mount: "center",
    render: renderScenePanel,
  });
  registerPanel({
    id: "map_placeholder",
    title: "Map Placeholder",
    group: "scene",
    mount: "center",
    render: renderMapPlaceholderPanel,
  });
  registerPanel({
    id: "round_log",
    title: "Round Log",
    group: "log",
    mount: "right",
    render: renderLogPanel,
  });
}

function mountPlayPanels() {
  const mounts = {
    campaign: document.getElementById("campaignMount"),
    left: document.getElementById("leftMount"),
    center: document.getElementById("centerMount"),
    right: document.getElementById("rightMount"),
  };

  const context = {
    setStatus,
    setBaseUrl,
    setCampaignId: changeCampaign,
    refreshCampaigns,
    createCampaign: createCampaignAndRefresh,
    setPartyActors,
    setPartyFromSummary,
    addSceneAction,
  };

  const render = () => {
    renderPanels({ mounts, state: getState(), context });
    renderStatusLine();
  };

  render();
  subscribe(render);
}

async function init() {
  initializeStore();
  registerPlayPanels();
  mountPlayPanels();
  setStatus("Loading campaigns...");
  await refreshCampaigns();
}

init();
