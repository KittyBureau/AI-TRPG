import { chatTurn, listCampaigns } from "./api/api.js";
import {
  appendDebugTrace,
  getState,
  initializeStore,
  setBaseUrl,
  setCampaignId,
  setCampaignOptions,
  setDebugRequestText,
  setDebugResponseText,
  setStatusMessage,
  subscribe,
  clearDebugTrace,
} from "./store/store.js";
import { clearPanelRegistry, registerPanel, renderPanels } from "./panels/registry.js";

const statusLine = document.getElementById("statusLine");

function setStatus(text) {
  setStatusMessage(text);
}

function renderStatusLine() {
  if (statusLine) {
    statusLine.textContent = getState().statusMessage || "Idle";
  }
}

function jsonPretty(value) {
  return JSON.stringify(value, null, 2);
}

function tryParseJson(text) {
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (error) {
    return { ok: false, error };
  }
}

async function copyText(text) {
  if (!navigator.clipboard) {
    return false;
  }
  await navigator.clipboard.writeText(text);
  return true;
}

function buildDefaultRequest() {
  const state = getState();
  return {
    campaign_id: state.campaignId || "camp_0001",
    user_input: "Describe the current scene.",
    execution: {
      actor_id: "pc_001",
    },
  };
}

async function refreshCampaigns() {
  const state = getState();
  const result = await listCampaigns(state.baseUrl);
  if (!result.ok || !result.data || !Array.isArray(result.data.campaigns)) {
    setStatus(`Failed to load campaigns (${result.status}).`);
    return;
  }
  setCampaignOptions(result.data.campaigns);
  const latestState = getState();
  if (!latestState.debug.requestText) {
    setDebugRequestText(jsonPretty(buildDefaultRequest()));
  }
  setStatus(`Loaded ${result.data.campaigns.length} campaigns.`);
}

async function sendRequestFromBuilder() {
  const state = getState();
  const parsed = tryParseJson(state.debug.requestText || "");
  if (!parsed.ok) {
    setStatus("Request JSON is invalid.");
    return;
  }

  const requestPayload = parsed.value;
  const result = await chatTurn(state.baseUrl, requestPayload);
  const responsePayload = result.data !== null ? result.data : result.text;
  const responseText = result.data !== null ? jsonPretty(result.data) : String(result.text);
  setDebugResponseText(responseText);

  appendDebugTrace({
    timestamp: new Date().toISOString(),
    request: requestPayload,
    response: responsePayload,
    status: result.status,
    ok: result.ok,
  });

  setStatus(`Request complete (${result.status}).`);
}

function exportBundle() {
  const state = getState();
  const bundle = {
    exported_at: new Date().toISOString(),
    base_url: state.baseUrl,
    traces: state.debug.traces,
  };
  const blob = new Blob([jsonPretty(bundle)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "debug_repro_bundle.json";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function renderRequestBuilderPanel(body, state, context) {
  const baseField = document.createElement("label");
  baseField.className = "field";
  baseField.innerHTML = '<span class="field-label">Base URL</span>';
  const baseInput = document.createElement("input");
  baseInput.placeholder = "http://127.0.0.1:8000";
  baseInput.value = state.baseUrl || "";
  baseInput.addEventListener("change", () => context.setBaseUrl(baseInput.value));
  baseField.appendChild(baseInput);

  const campaignField = document.createElement("label");
  campaignField.className = "field";
  campaignField.innerHTML = '<span class="field-label">Campaign</span>';
  const campaignControls = document.createElement("div");
  campaignControls.className = "inline";
  const campaignSelect = document.createElement("select");
  for (const campaign of state.campaignOptions) {
    const option = document.createElement("option");
    option.value = campaign.id;
    option.textContent = `${campaign.id} (active=${campaign.active_actor_id})`;
    option.selected = campaign.id === state.campaignId;
    campaignSelect.appendChild(option);
  }
  campaignSelect.addEventListener("change", () => {
    context.setCampaignId(campaignSelect.value);
  });
  const refreshBtn = document.createElement("button");
  refreshBtn.className = "ghost";
  refreshBtn.textContent = "Refresh";
  refreshBtn.addEventListener("click", context.refreshCampaigns);
  campaignControls.appendChild(campaignSelect);
  campaignControls.appendChild(refreshBtn);
  campaignField.appendChild(campaignControls);

  const requestField = document.createElement("label");
  requestField.className = "field";
  requestField.innerHTML = '<span class="field-label">Request Builder (raw JSON)</span>';
  const requestInput = document.createElement("textarea");
  requestInput.rows = 12;
  requestInput.value = state.debug.requestText || "";
  requestInput.addEventListener("input", () => {
    context.setDebugRequestText(requestInput.value, { emit: false });
  });
  requestField.appendChild(requestInput);

  const actions = document.createElement("div");
  actions.className = "inline";

  const templateBtn = document.createElement("button");
  templateBtn.className = "ghost";
  templateBtn.textContent = "Load Template";
  templateBtn.addEventListener("click", () => {
    context.setDebugRequestText(jsonPretty(buildDefaultRequest()));
  });

  const copyBtn = document.createElement("button");
  copyBtn.className = "ghost";
  copyBtn.textContent = "Copy Request";
  copyBtn.addEventListener("click", async () => {
    await copyText(requestInput.value || "");
    context.setStatus("Request copied.");
  });

  const sendBtn = document.createElement("button");
  sendBtn.textContent = "Send /chat/turn";
  sendBtn.addEventListener("click", context.sendRequest);

  actions.appendChild(templateBtn);
  actions.appendChild(copyBtn);
  actions.appendChild(sendBtn);

  body.appendChild(baseField);
  body.appendChild(campaignField);
  body.appendChild(requestField);
  body.appendChild(actions);
}

function renderResponseViewerPanel(body, state, context) {
  const response = document.createElement("pre");
  response.className = "raw";
  response.textContent = state.debug.responseText || "No response yet.";

  const actions = document.createElement("div");
  actions.className = "inline";

  const copyBtn = document.createElement("button");
  copyBtn.className = "ghost";
  copyBtn.textContent = "Copy Response";
  copyBtn.addEventListener("click", async () => {
    await copyText(state.debug.responseText || "");
    context.setStatus("Response copied.");
  });

  actions.appendChild(copyBtn);
  body.appendChild(actions);
  body.appendChild(response);
}

function renderTraceLogPanel(body, state, context) {
  const actions = document.createElement("div");
  actions.className = "inline";

  const exportBtn = document.createElement("button");
  exportBtn.textContent = "Export Reproduction Bundle";
  exportBtn.addEventListener("click", context.exportBundle);

  const clearBtn = document.createElement("button");
  clearBtn.className = "danger";
  clearBtn.textContent = "Clear Trace";
  clearBtn.addEventListener("click", context.clearTrace);

  actions.appendChild(exportBtn);
  actions.appendChild(clearBtn);
  body.appendChild(actions);

  if (!state.debug.traces.length) {
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "No traces yet.";
    body.appendChild(note);
    return;
  }

  for (const trace of [...state.debug.traces].reverse()) {
    const card = document.createElement("div");
    card.className = "trace-entry";

    const meta = document.createElement("div");
    meta.className = "trace-meta";
    meta.textContent = `${trace.timestamp} | status=${trace.status}`;

    const request = document.createElement("pre");
    request.className = "raw";
    request.textContent = jsonPretty(trace.request);

    const response = document.createElement("pre");
    response.className = "raw";
    response.textContent = jsonPretty(trace.response);

    card.appendChild(meta);
    card.appendChild(request);
    card.appendChild(response);
    body.appendChild(card);
  }
}

function registerDebugPanels() {
  clearPanelRegistry();
  registerPanel({
    id: "request_builder",
    title: "Request Builder",
    group: "debug",
    mount: "left",
    render: renderRequestBuilderPanel,
  });
  registerPanel({
    id: "response_viewer",
    title: "Response Viewer",
    group: "debug",
    mount: "right",
    render: renderResponseViewerPanel,
  });
  registerPanel({
    id: "trace_log",
    title: "Trace Log",
    group: "debug",
    mount: "right",
    render: renderTraceLogPanel,
  });
}

function mountDebugPanels() {
  const mounts = {
    left: document.getElementById("debugLeftMount"),
    right: document.getElementById("debugRightMount"),
  };

  const context = {
    setStatus,
    setBaseUrl,
    setCampaignId,
    refreshCampaigns,
    sendRequest: sendRequestFromBuilder,
    setDebugRequestText,
    exportBundle,
    clearTrace: clearDebugTrace,
  };

  const render = () => renderPanels({ mounts, state: getState(), context });
  const renderWithStatus = () => {
    render();
    renderStatusLine();
  };
  renderWithStatus();
  subscribe(renderWithStatus);
}

async function init() {
  initializeStore();
  registerDebugPanels();
  mountDebugPanels();
  setStatus("Loading debug data...");
  await refreshCampaigns();
  if (!getState().debug.requestText) {
    setDebugRequestText(jsonPretty(buildDefaultRequest()));
  }
  setStatus("Debug page ready.");
}

init();
