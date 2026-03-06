import { chatTurn, listCampaigns } from "./api/api.js";
import {
  appendDebugTrace,
  checkBackendReady,
  getState,
  initializeStore,
  recoverFrontendSession,
  setBaseUrl,
  setCampaignId,
  setCampaignOptions,
  setDebugRequestText,
  setDebugResponseText,
  setStatusMessage,
  subscribe,
  clearDebugTrace,
} from "./store/store.js";
import {
  extractDebugResourcesFromResponseText,
  formatResourceEntry,
  RESOURCE_CATEGORIES,
} from "./utils/debug_resources.js";
import { clearPanelRegistry, registerPanel, renderPanels } from "./panels/registry.js";

const statusLine = document.getElementById("statusLine");

function captureFocusState(...roots) {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement)) {
    return null;
  }
  const key = active.getAttribute("data-focus-key");
  if (!key) {
    return null;
  }
  if (!roots.some((root) => root instanceof HTMLElement && root.contains(active))) {
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

function restoreFocusState(snapshot, ...roots) {
  if (!snapshot) {
    return;
  }
  for (const root of roots) {
    if (!(root instanceof HTMLElement)) {
      continue;
    }
    const target = root.querySelector(`[data-focus-key="${snapshot.key}"]`);
    if (!(target instanceof HTMLElement)) {
      continue;
    }
    target.focus();
    if (
      typeof snapshot.selectionStart === "number" &&
      typeof snapshot.selectionEnd === "number" &&
      "setSelectionRange" in target
    ) {
      target.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd);
    }
    return;
  }
}

function setStatus(text) {
  setStatusMessage(text);
}

function renderStatusLine() {
  if (statusLine) {
    statusLine.textContent = getState().statusMessage || "Idle";
  }
}

function startReadinessPolling() {
  window.setInterval(async () => {
    const state = getState();
    if (!state.baseUrl || state.backend?.ready !== false) {
      return;
    }
    const recovered = await recoverRuntime({ silent: true, manual: false });
    if (recovered) {
      setStatus("Backend unlocked. Debug page recovered.");
    }
  }, 3000);
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

let recoverPromise = null;

function recoverRuntime({ silent = false, manual = false } = {}) {
  if (recoverPromise) {
    return recoverPromise;
  }
  recoverPromise = (async () => {
    const recovered = await recoverFrontendSession(getState().baseUrl, {
      silent,
      loadCharacterLibrary: false,
    });
    if (!recovered.ok) {
      return false;
    }
    if (!getState().debug.requestText) {
      setDebugRequestText(jsonPretty(buildDefaultRequest()));
    }
    if (manual) {
      setStatus("Backend ready. Debug data reloaded.");
    }
    return true;
  })();
  recoverPromise = recoverPromise.finally(() => {
    recoverPromise = null;
  });
  return recoverPromise;
}

async function sendRequestFromBuilder() {
  const state = getState();
  if (state.baseUrl) {
    const readiness = await checkBackendReady(state.baseUrl, { silent: false });
    if (readiness.ready === false) {
      return;
    }
  }
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
  baseInput.setAttribute("data-focus-key", "debug-base-url");
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
  campaignSelect.setAttribute("data-focus-key", "debug-campaign-select");
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
  requestInput.setAttribute("data-focus-key", "debug-request-input");
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

  const retryBtn = document.createElement("button");
  retryBtn.className = "ghost";
  retryBtn.textContent = "Retry Connection";
  retryBtn.addEventListener("click", async () => {
    await context.recoverRuntime({ silent: false, manual: true });
  });

  actions.appendChild(templateBtn);
  actions.appendChild(copyBtn);
  actions.appendChild(retryBtn);
  actions.appendChild(sendBtn);

  body.appendChild(baseField);
  body.appendChild(campaignField);
  body.appendChild(requestField);
  body.appendChild(actions);
}

function renderResponseViewerPanel(body, state, context) {
  const resourcesTitle = document.createElement("h3");
  resourcesTitle.textContent = "Debug Resources";
  body.appendChild(resourcesTitle);

  const resourcesView = extractDebugResourcesFromResponseText(state.debug.responseText || "");
  const resourcesNote = document.createElement("div");
  resourcesNote.className = "note";
  if (!resourcesView.available) {
    resourcesNote.textContent = resourcesView.reason || "trace disabled / no debug";
    body.appendChild(resourcesNote);
  } else {
    resourcesNote.textContent =
      resourcesView.source === "resources"
        ? "Source: debug.resources"
        : "Source: legacy debug fields";
    body.appendChild(resourcesNote);

    for (const category of RESOURCE_CATEGORIES) {
      const entries = Array.isArray(resourcesView.resources?.[category])
        ? resourcesView.resources[category]
        : [];
      const sectionTitle = document.createElement("div");
      sectionTitle.className = "note";
      sectionTitle.textContent = `${category} (${entries.length})`;
      body.appendChild(sectionTitle);
      if (!entries.length) {
        const empty = document.createElement("div");
        empty.className = "row note";
        empty.textContent = "(empty)";
        body.appendChild(empty);
        continue;
      }
      for (const entry of entries) {
        const row = document.createElement("div");
        row.className = "row";
        row.textContent = formatResourceEntry(category, entry);
        body.appendChild(row);
      }
    }
  }

  const rawTitle = document.createElement("h3");
  rawTitle.textContent = "Raw Response";
  body.appendChild(rawTitle);

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
    setBaseUrl: async (value) => {
      setBaseUrl(value);
      if (getState().baseUrl) {
        await recoverRuntime({ silent: false, manual: true });
      }
    },
    setCampaignId,
    refreshCampaigns,
    sendRequest: sendRequestFromBuilder,
    setDebugRequestText,
    exportBundle,
    clearTrace: clearDebugTrace,
    recoverRuntime,
  };

  const render = () => renderPanels({ mounts, state: getState(), context });
  const renderWithStatus = () => {
    const focusSnapshot = captureFocusState(mounts.left, mounts.right);
    render();
    restoreFocusState(focusSnapshot, mounts.left, mounts.right);
    renderStatusLine();
  };
  renderWithStatus();
  subscribe(renderWithStatus);
}

async function init() {
  initializeStore();
  registerDebugPanels();
  mountDebugPanels();
  startReadinessPolling();
  if (!getState().debug.requestText) {
    setDebugRequestText(jsonPretty(buildDefaultRequest()));
  }
  if (getState().baseUrl) {
    const recovered = await recoverRuntime({ silent: false, manual: false });
    if (!recovered && getState().backend.ready !== false) {
      setStatus("Debug page ready.");
    }
  } else {
    setStatus("Debug page ready.");
  }
}

void init();
