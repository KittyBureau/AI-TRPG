const HISTORY_KEY = "raw-console-history";
const BASE_URL_KEY = "raw-console-base-url";
const HISTORY_LIMIT = 200;

const elements = {
  statusLine: document.getElementById("statusLine"),
  baseUrl: document.getElementById("baseUrl"),
  campaignSelect: document.getElementById("campaignSelect"),
  refreshCampaigns: document.getElementById("refreshCampaigns"),
  saveSettings: document.getElementById("saveSettings"),
  createCampaignRaw: document.getElementById("createCampaignRaw"),
  createCampaignBtn: document.getElementById("createCampaignBtn"),
  activeActorInput: document.getElementById("activeActorInput"),
  applyActorToRaw: document.getElementById("applyActorToRaw"),
  selectActorRaw: document.getElementById("selectActorRaw"),
  selectActorBtn: document.getElementById("selectActorBtn"),
  turnRaw: document.getElementById("turnRaw"),
  turnUserInput: document.getElementById("turnUserInput"),
  applyUserInput: document.getElementById("applyUserInput"),
  sendTurn: document.getElementById("sendTurn"),
  turnNarrative: document.getElementById("turnNarrative"),
  turnDialogType: document.getElementById("turnDialogType"),
  turnToolCalls: document.getElementById("turnToolCalls"),
  turnAppliedActions: document.getElementById("turnAppliedActions"),
  turnToolFeedback: document.getElementById("turnToolFeedback"),
  turnConflictReport: document.getElementById("turnConflictReport"),
  turnStateSummary: document.getElementById("turnStateSummary"),
  turnRawResponse: document.getElementById("turnRawResponse"),
  loadSchema: document.getElementById("loadSchema"),
  settingsDefinitions: document.getElementById("settingsDefinitions"),
  settingsSnapshot: document.getElementById("settingsSnapshot"),
  settingsPatchRaw: document.getElementById("settingsPatchRaw"),
  applySettings: document.getElementById("applySettings"),
  settingsApplySnapshot: document.getElementById("settingsApplySnapshot"),
  settingsApplySummary: document.getElementById("settingsApplySummary"),
  settingsApplyRaw: document.getElementById("settingsApplyRaw"),
  exportHistory: document.getElementById("exportHistory"),
  clearHistory: document.getElementById("clearHistory"),
  historyList: document.getElementById("historyList"),
};

const state = {
  currentCampaignId: "",
  lastCampaignId: "",
  history: [],
};

function setStatus(message) {
  elements.statusLine.textContent = message;
}

function safeJsonParse(text) {
  if (typeof text !== "string") {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    return null;
  }
}

function formatField(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  return JSON.stringify(value, null, 2);
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch (error) {
    return [];
  }
}

function saveHistory() {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(state.history));
  } catch (error) {
    setStatus("History could not be saved.");
  }
}

function addHistory(entry) {
  state.history.unshift(entry);
  if (state.history.length > HISTORY_LIMIT) {
    state.history = state.history.slice(0, HISTORY_LIMIT);
  }
  saveHistory();
  renderHistory();
}

function renderHistory() {
  elements.historyList.innerHTML = "";
  if (!state.history.length) {
    const empty = document.createElement("div");
    empty.textContent = "No requests yet.";
    elements.historyList.appendChild(empty);
    return;
  }

  state.history.forEach((entry, index) => {
    const details = document.createElement("details");
    details.className = "history-item";
    details.open = index === 0;

    const summary = document.createElement("summary");
    summary.textContent = `${entry.timestamp} | ${entry.endpoint} | ${entry.status} | ${entry.latency}ms`;
    details.appendChild(summary);

    const meta = document.createElement("div");
    meta.className = "history-meta";
    meta.textContent = entry.url ? `URL: ${entry.url}` : "URL: (relative)";
    details.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "history-actions";

    const copyReq = document.createElement("button");
    copyReq.className = "ghost";
    copyReq.dataset.copy = "request";
    copyReq.dataset.index = index;
    copyReq.textContent = "Copy Request";

    const copyRes = document.createElement("button");
    copyRes.className = "ghost";
    copyRes.dataset.copy = "response";
    copyRes.dataset.index = index;
    copyRes.textContent = "Copy Response";

    actions.appendChild(copyReq);
    actions.appendChild(copyRes);
    details.appendChild(actions);

    const reqLabel = document.createElement("div");
    reqLabel.textContent = "Request Raw";
    const reqPre = document.createElement("pre");
    reqPre.textContent = entry.requestRaw || "";

    const resLabel = document.createElement("div");
    resLabel.textContent = "Response Raw";
    const resPre = document.createElement("pre");
    resPre.textContent = entry.responseRaw || "";

    details.appendChild(reqLabel);
    details.appendChild(reqPre);
    details.appendChild(resLabel);
    details.appendChild(resPre);

    elements.historyList.appendChild(details);
  });
}

function getBaseUrl() {
  const raw = elements.baseUrl.value.trim();
  if (!raw) {
    return "";
  }
  return raw.replace(/\/+$/, "");
}

function buildUrl(path) {
  const base = getBaseUrl();
  if (!base) {
    return path;
  }
  if (path.startsWith("/")) {
    return `${base}${path}`;
  }
  return `${base}/${path}`;
}

function ensureCampaignOption(campaignId) {
  if (!campaignId) {
    return;
  }
  const existing = Array.from(elements.campaignSelect.options).some(
    (option) => option.value === campaignId
  );
  if (!existing) {
    const option = document.createElement("option");
    option.value = campaignId;
    option.textContent = `Manual: ${campaignId}`;
    elements.campaignSelect.appendChild(option);
  }
}

function updateCampaignIdInRaw(textarea, previousId, nextId) {
  const raw = textarea.value;
  const parsed = safeJsonParse(raw);
  if (!parsed || typeof parsed !== "object") {
    return;
  }
  if (!Object.prototype.hasOwnProperty.call(parsed, "campaign_id")) {
    return;
  }
  const currentValue = parsed.campaign_id;
  const shouldReplace =
    currentValue === previousId ||
    currentValue === "<current>" ||
    currentValue === "" ||
    currentValue === null;
  if (!shouldReplace) {
    return;
  }
  parsed.campaign_id = nextId || "";
  textarea.value = JSON.stringify(parsed, null, 2);
}

function syncCampaignIdToRawEditors(previousId, nextId) {
  updateCampaignIdInRaw(elements.turnRaw, previousId, nextId);
  updateCampaignIdInRaw(elements.selectActorRaw, previousId, nextId);
}

function setCurrentCampaignId(campaignId) {
  state.lastCampaignId = state.currentCampaignId;
  state.currentCampaignId = campaignId || "";
  ensureCampaignOption(state.currentCampaignId);
  elements.campaignSelect.value = state.currentCampaignId;
  syncCampaignIdToRawEditors(state.lastCampaignId, state.currentCampaignId);
}

function extractCampaignIdFromResponse(data) {
  if (!data) {
    return "";
  }
  if (typeof data === "string" || typeof data === "number") {
    return String(data);
  }
  if (typeof data !== "object") {
    return "";
  }
  if (data.campaign_id) {
    return String(data.campaign_id);
  }
  if (data.id) {
    return String(data.id);
  }
  if (data.campaign && data.campaign.campaign_id) {
    return String(data.campaign.campaign_id);
  }
  if (data.data && data.data.campaign_id) {
    return String(data.data.campaign_id);
  }
  return "";
}

function extractCampaignList(data) {
  if (!data) {
    return [];
  }
  if (Array.isArray(data)) {
    return data;
  }
  if (Array.isArray(data.campaigns)) {
    return data.campaigns;
  }
  if (Array.isArray(data.items)) {
    return data.items;
  }
  if (Array.isArray(data.data)) {
    return data.data;
  }
  return [];
}

function campaignOptionFromItem(item) {
  if (item === null || item === undefined) {
    return null;
  }
  if (typeof item === "string" || typeof item === "number") {
    return { id: String(item), label: String(item) };
  }
  if (typeof item === "object") {
    const id =
      item.campaign_id || item.id || item.uuid || item.key || item.value;
    if (!id) {
      return null;
    }
    const name = item.name || item.title || "";
    const label = name ? `${id} - ${name}` : String(id);
    return { id: String(id), label };
  }
  return null;
}

function setPreValue(target, value) {
  target.textContent = value || "";
}

function renderTurnResponse(rawText) {
  const data = safeJsonParse(rawText);
  setPreValue(elements.turnRawResponse, rawText || "");
  if (!data) {
    setPreValue(elements.turnNarrative, "");
    setPreValue(elements.turnDialogType, "");
    setPreValue(elements.turnToolCalls, "");
    setPreValue(elements.turnAppliedActions, "");
    setPreValue(elements.turnToolFeedback, "");
    setPreValue(elements.turnConflictReport, "");
    setPreValue(elements.turnStateSummary, "");
    return;
  }
  setPreValue(elements.turnNarrative, formatField(data.narrative_text));
  setPreValue(elements.turnDialogType, formatField(data.dialog_type));
  setPreValue(elements.turnToolCalls, formatField(data.tool_calls));
  setPreValue(elements.turnAppliedActions, formatField(data.applied_actions));
  setPreValue(elements.turnToolFeedback, formatField(data.tool_feedback));
  setPreValue(elements.turnConflictReport, formatField(data.conflict_report));
  setPreValue(elements.turnStateSummary, formatField(data.state_summary));
}

function buildSettingsApplyBody(campaignId, patchRaw) {
  const trimmed = patchRaw.trim();
  const idJson = JSON.stringify(campaignId || "");
  if (!trimmed) {
    return `{"campaign_id":${idJson},"patch":{}}`;
  }
  const parsed = safeJsonParse(trimmed);
  if (parsed !== null) {
    return JSON.stringify(
      {
        campaign_id: campaignId || "",
        patch: parsed,
      },
      null,
      2
    );
  }
  return `{"campaign_id":${idJson},"patch":${patchRaw}}`;
}

async function sendRequest({ method, path, bodyText }) {
  const url = buildUrl(path);
  const start =
    typeof performance !== "undefined" && performance.now
      ? performance.now()
      : Date.now();
  let latency = 0;
  let status = "ERROR";
  let responseText = "";
  let ok = false;

  setStatus(`${method} ${path} ...`);
  try {
    const headers = {};
    if (bodyText !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    const response = await fetch(url, {
      method,
      headers,
      body: bodyText,
    });
    responseText = await response.text();
    status = response.status;
    ok = response.ok;
    latency =
      (typeof performance !== "undefined" && performance.now
        ? performance.now()
        : Date.now()) - start;
  } catch (error) {
    responseText = error && error.stack ? error.stack : String(error);
    status = "FETCH_ERROR";
    latency =
      (typeof performance !== "undefined" && performance.now
        ? performance.now()
        : Date.now()) - start;
  }

  const entry = {
    timestamp: new Date().toISOString(),
    endpoint: `${method} ${path}`,
    url,
    status,
    latency: Math.round(latency),
    requestRaw: bodyText !== undefined ? bodyText : "",
    responseRaw: responseText,
  };
  addHistory(entry);
  setStatus(`${method} ${path} -> ${status} in ${Math.round(latency)}ms`);

  return { ok, status, responseText };
}

function applyUserInputToRaw() {
  const raw = elements.turnRaw.value;
  const parsed = safeJsonParse(raw);
  if (!parsed || typeof parsed !== "object") {
    setStatus("Apply failed: turn raw is not JSON.");
    return;
  }
  parsed.user_input = elements.turnUserInput.value;
  elements.turnRaw.value = JSON.stringify(parsed, null, 2);
  setStatus("Applied user_input to raw.");
}

function applyActorToRaw() {
  const raw = elements.selectActorRaw.value;
  const parsed = safeJsonParse(raw);
  if (!parsed || typeof parsed !== "object") {
    setStatus("Apply failed: actor raw is not JSON.");
    return;
  }
  parsed.actor_id = elements.activeActorInput.value;
  elements.selectActorRaw.value = JSON.stringify(parsed, null, 2);
  setStatus("Applied actor_id to raw.");
}

async function refreshCampaigns() {
  const result = await sendRequest({
    method: "GET",
    path: "/api/campaign/list",
  });
  const data = safeJsonParse(result.responseText);
  if (!data) {
    return;
  }
  const list = extractCampaignList(data);
  const options = list
    .map(campaignOptionFromItem)
    .filter((item) => item && item.id);

  elements.campaignSelect.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select campaign...";
  elements.campaignSelect.appendChild(placeholder);

  options.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = item.label;
    elements.campaignSelect.appendChild(option);
  });

  ensureCampaignOption(state.currentCampaignId);
  elements.campaignSelect.value = state.currentCampaignId || "";
}

async function createCampaign() {
  const raw = elements.createCampaignRaw.value;
  const result = await sendRequest({
    method: "POST",
    path: "/api/campaign/create",
    bodyText: raw,
  });
  const data = safeJsonParse(result.responseText);
  const campaignId = extractCampaignIdFromResponse(data);
  if (campaignId) {
    setCurrentCampaignId(campaignId);
  }
}

async function selectActor() {
  const raw = elements.selectActorRaw.value;
  await sendRequest({
    method: "POST",
    path: "/api/campaign/select_actor",
    bodyText: raw,
  });
}

async function sendTurn() {
  const raw = elements.turnRaw.value;
  const result = await sendRequest({
    method: "POST",
    path: "/api/chat/turn",
    bodyText: raw,
  });
  renderTurnResponse(result.responseText);
}

async function loadSchema() {
  const query = new URLSearchParams({
    campaign_id: state.currentCampaignId || "",
  });
  const result = await sendRequest({
    method: "GET",
    path: `/api/settings/schema?${query.toString()}`,
  });
  const data = safeJsonParse(result.responseText);
  if (!data) {
    setPreValue(elements.settingsDefinitions, "");
    setPreValue(elements.settingsSnapshot, "");
    return;
  }
  setPreValue(elements.settingsDefinitions, formatField(data.definitions));
  setPreValue(elements.settingsSnapshot, formatField(data.snapshot));
}

async function applySettings() {
  const patchRaw = elements.settingsPatchRaw.value;
  const bodyText = buildSettingsApplyBody(state.currentCampaignId, patchRaw);
  const result = await sendRequest({
    method: "POST",
    path: "/api/settings/apply",
    bodyText,
  });
  const data = safeJsonParse(result.responseText);
  setPreValue(elements.settingsApplyRaw, result.responseText || "");
  if (!data) {
    setPreValue(elements.settingsApplySnapshot, "");
    setPreValue(elements.settingsApplySummary, "");
    return;
  }
  setPreValue(elements.settingsApplySnapshot, formatField(data.snapshot));
  setPreValue(
    elements.settingsApplySummary,
    formatField(data.change_summary)
  );
}

function exportHistory() {
  const blob = new Blob([JSON.stringify(state.history, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  anchor.href = url;
  anchor.download = `raw-console-history-${stamp}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

function clearHistory() {
  state.history = [];
  saveHistory();
  renderHistory();
}

function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text);
    return;
  }
  const helper = document.createElement("textarea");
  helper.value = text;
  document.body.appendChild(helper);
  helper.select();
  document.execCommand("copy");
  document.body.removeChild(helper);
}

function bindEvents() {
  elements.baseUrl.addEventListener("change", () => {
    localStorage.setItem(BASE_URL_KEY, getBaseUrl());
  });

  elements.campaignSelect.addEventListener("change", (event) => {
    setCurrentCampaignId(event.target.value);
  });

  elements.refreshCampaigns.addEventListener("click", refreshCampaigns);
  elements.saveSettings.addEventListener("click", () => {
    const baseUrl = getBaseUrl();
    if (baseUrl) {
      localStorage.setItem(BASE_URL_KEY, baseUrl);
      setStatus(`Saved Base URL: ${baseUrl}`);
    } else {
      localStorage.removeItem(BASE_URL_KEY);
      setStatus("Saved: Base URL cleared.");
    }
  });
  elements.createCampaignBtn.addEventListener("click", createCampaign);
  elements.applyActorToRaw.addEventListener("click", applyActorToRaw);
  elements.selectActorBtn.addEventListener("click", selectActor);
  elements.applyUserInput.addEventListener("click", applyUserInputToRaw);
  elements.sendTurn.addEventListener("click", sendTurn);
  elements.loadSchema.addEventListener("click", loadSchema);
  elements.applySettings.addEventListener("click", applySettings);
  elements.exportHistory.addEventListener("click", exportHistory);
  elements.clearHistory.addEventListener("click", clearHistory);

  elements.historyList.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) {
      return;
    }
    const copyType = target.dataset.copy;
    const index = target.dataset.index;
    if (!copyType || index === undefined) {
      return;
    }
    const entry = state.history[Number(index)];
    if (!entry) {
      return;
    }
    const text = copyType === "request" ? entry.requestRaw : entry.responseRaw;
    copyText(text || "");
    setStatus(`Copied ${copyType}.`);
  });
}

function initTemplates() {
  elements.createCampaignRaw.value = JSON.stringify(
    {
      world_id: "",
      map_id: "",
      party_character_ids: [],
      active_actor_id: "",
    },
    null,
    2
  );

  elements.selectActorRaw.value = JSON.stringify(
    {
      campaign_id: "<current>",
      actor_id: "",
    },
    null,
    2
  );

  elements.turnRaw.value = JSON.stringify(
    {
      campaign_id: "<current>",
      user_input: "",
      actor_id: "",
    },
    null,
    2
  );

  elements.settingsPatchRaw.value = '{ "dialog.auto_type_enabled": false }';
}

function init() {
  state.history = loadHistory();
  renderHistory();
  initTemplates();

  const savedBaseUrl = localStorage.getItem(BASE_URL_KEY);
  if (savedBaseUrl) {
    elements.baseUrl.value = savedBaseUrl;
  }

  bindEvents();
  setStatus("Ready.");
}

init();
