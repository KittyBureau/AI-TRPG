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
  turnGuardInsight: document.getElementById("turnGuardInsight"),
  turnNarrative: document.getElementById("turnNarrative"),
  turnDialogType: document.getElementById("turnDialogType"),
  turnToolCalls: document.getElementById("turnToolCalls"),
  turnAppliedActions: document.getElementById("turnAppliedActions"),
  turnToolFeedback: document.getElementById("turnToolFeedback"),
  turnConflictReport: document.getElementById("turnConflictReport"),
  turnStateSummary: document.getElementById("turnStateSummary"),
  turnRawResponse: document.getElementById("turnRawResponse"),
  worldIdInput: document.getElementById("worldIdInput"),
  worldBindToCampaign: document.getElementById("worldBindToCampaign"),
  runWorldGenerate: document.getElementById("runWorldGenerate"),
  worldGenerateResult: document.getElementById("worldGenerateResult"),
  mapParentAreaInput: document.getElementById("mapParentAreaInput"),
  mapThemeInput: document.getElementById("mapThemeInput"),
  mapSizeInput: document.getElementById("mapSizeInput"),
  mapSeedInput: document.getElementById("mapSeedInput"),
  runMapGenerate: document.getElementById("runMapGenerate"),
  mapGenerateResult: document.getElementById("mapGenerateResult"),
  spawnCharacterIdInput: document.getElementById("spawnCharacterIdInput"),
  spawnPositionInput: document.getElementById("spawnPositionInput"),
  spawnBindToParty: document.getElementById("spawnBindToParty"),
  runActorSpawn: document.getElementById("runActorSpawn"),
  actorSpawnResult: document.getElementById("actorSpawnResult"),
  moveActorIdInput: document.getElementById("moveActorIdInput"),
  moveToAreaInput: document.getElementById("moveToAreaInput"),
  runMove: document.getElementById("runMove"),
  moveResult: document.getElementById("moveResult"),
  flowCurrentActor: document.getElementById("flowCurrentActor"),
  flowCurrentPosition: document.getElementById("flowCurrentPosition"),
  flowNarrative: document.getElementById("flowNarrative"),
  flowObjective: document.getElementById("flowObjective"),
  flowAreaDescription: document.getElementById("flowAreaDescription"),
  flowInventory: document.getElementById("flowInventory"),
  flowRetryCount: document.getElementById("flowRetryCount"),
  runFlowCreateCampaign: document.getElementById("runFlowCreateCampaign"),
  runFlowWorld: document.getElementById("runFlowWorld"),
  runFlowMap: document.getElementById("runFlowMap"),
  runFlowSpawn: document.getElementById("runFlowSpawn"),
  runFlowMove: document.getElementById("runFlowMove"),
  runFlowTurn: document.getElementById("runFlowTurn"),
  runFullFlow: document.getElementById("runFullFlow"),
  narrativeTurnInput: document.getElementById("narrativeTurnInput"),
  narrativeTurnResult: document.getElementById("narrativeTurnResult"),
  flowResult: document.getElementById("flowResult"),
  errorInspector: document.getElementById("errorInspector"),
  fetchCampaignStatus: document.getElementById("fetchCampaignStatus"),
  refreshAfterTurn: document.getElementById("refreshAfterTurn"),
  campaignLifecycle: document.getElementById("campaignLifecycle"),
  campaignMilestone: document.getElementById("campaignMilestone"),
  activeActorState: document.getElementById("activeActorState"),
  settingsFocusView: document.getElementById("settingsFocusView"),
  milestoneSummaryInput: document.getElementById("milestoneSummaryInput"),
  advanceMilestoneBtn: document.getElementById("advanceMilestoneBtn"),
  advanceMilestoneResult: document.getElementById("advanceMilestoneResult"),
  adoptCharacterId: document.getElementById("adoptCharacterId"),
  acceptedByInput: document.getElementById("acceptedByInput"),
  adoptFactBtn: document.getElementById("adoptFactBtn"),
  adoptFactResult: document.getElementById("adoptFactResult"),
  generateCharacterRaw: document.getElementById("generateCharacterRaw"),
  generateCharacterBtn: document.getElementById("generateCharacterBtn"),
  generateCharacterResult: document.getElementById("generateCharacterResult"),
  runLoopBtn: document.getElementById("runLoopBtn"),
  runLoopResult: document.getElementById("runLoopResult"),
  toggleStrictGuard: document.getElementById("toggleStrictGuard"),
  toggleConflictTextChecks: document.getElementById("toggleConflictTextChecks"),
  toggleCompressEnabled: document.getElementById("toggleCompressEnabled"),
  applyFocusToggles: document.getElementById("applyFocusToggles"),
  toggleApplyResult: document.getElementById("toggleApplyResult"),
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
  autoRefreshStatusAfterTurn: false,
  latestTurnStateSummary: null,
  latestTurnResponse: null,
  latestSettingsSnapshot: null,
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

function buildErrorSuggestion(status, detail) {
  const text = String(detail || "").toLowerCase();
  if (status === 422 && text.includes("invalid dialog_type")) {
    return "Suggestion: strict_semantic_guard is ON; disable it in settings or ensure model emits allowed dialog_type.";
  }
  if (status === 400 && text.includes("campaign has ended")) {
    return "Suggestion: campaign ended is read-only for turns; use Campaign Status to inspect lifecycle and create/switch to another campaign.";
  }
  if (status === 400 && text.includes("unconscious")) {
    return "Suggestion: switch actor via /api/v1/campaign/select_actor, then retry turn.";
  }
  if (text.includes("repeat_illegal_request")) {
    return "Suggestion: change tool args or wait beyond repeated failure window before retrying.";
  }
  if (status === 404 && text.includes("characterfact")) {
    return "Suggestion: ensure campaign_id and character_id exist and fact draft/batch is available.";
  }
  if (status === 409) {
    return "Suggestion: duplicate request detected; use a new request_id or refresh current state.";
  }
  if (status >= 400) {
    return "Suggestion: check payload and current campaign state, then retry.";
  }
  return "";
}

function renderErrorInspector(status, responseText) {
  const parsed = safeJsonParse(responseText);
  const detail =
    parsed && typeof parsed === "object" && "detail" in parsed
      ? parsed.detail
      : responseText || "";
  const suggestion = buildErrorSuggestion(Number(status), detail);
  const payload = {
    status,
    detail,
    suggestion,
  };
  setPreValue(elements.errorInspector, formatField(payload));
}

function applySettingsFocusSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") {
    setPreValue(elements.settingsFocusView, "");
    return;
  }
  state.latestSettingsSnapshot = snapshot;
  const focus = {
    "dialog.strict_semantic_guard":
      snapshot.dialog && snapshot.dialog.strict_semantic_guard,
    "dialog.conflict_text_checks_enabled":
      snapshot.dialog && snapshot.dialog.conflict_text_checks_enabled,
    "context.compress_enabled":
      snapshot.context && snapshot.context.compress_enabled,
    context_mode_inference:
      snapshot.context && snapshot.context.compress_enabled ? "compressed" : "full",
  };
  setPreValue(elements.settingsFocusView, formatField(focus));
}

function renderCampaignStatusPanel(statusPayload) {
  if (!statusPayload || typeof statusPayload !== "object") {
    setPreValue(elements.campaignLifecycle, "");
    setPreValue(elements.campaignMilestone, "");
    return;
  }
  setPreValue(
    elements.campaignLifecycle,
    formatField({
      ended: statusPayload.ended,
      reason: statusPayload.reason || null,
      ended_at: statusPayload.ended_at || null,
    })
  );
  setPreValue(elements.campaignMilestone, formatField(statusPayload.milestone || {}));
}

function renderActiveActorStateFromSummary(summary) {
  if (!summary || typeof summary !== "object") {
    setPreValue(elements.activeActorState, "");
    return;
  }
  const actorId = summary.active_actor_id || "";
  const payload = {
    active_actor_id: actorId,
    position: summary.positions ? summary.positions[actorId] : undefined,
    area_name: summary.active_area_name || undefined,
    area_description: summary.active_area_description || undefined,
    hp: summary.hp ? summary.hp[actorId] : undefined,
    character_state: summary.character_states
      ? summary.character_states[actorId]
      : undefined,
    inventory: summary.active_actor_inventory || {},
    objective: summary.objective || undefined,
  };
  state.latestTurnStateSummary = summary;
  setPreValue(elements.activeActorState, formatField(payload));
}

function renderGameplaySnapshot(turnData) {
  if (!turnData || typeof turnData !== "object") {
    setPreValue(elements.flowCurrentActor, "");
    setPreValue(elements.flowCurrentPosition, "");
    setPreValue(elements.flowNarrative, "");
    setPreValue(elements.flowObjective, "");
    setPreValue(elements.flowAreaDescription, "");
    setPreValue(elements.flowInventory, "");
    return;
  }
  const summary = turnData.state_summary || {};
  const actorId = summary.active_actor_id || "";
  const areaName = summary.active_area_name || "";
  const areaId = summary.active_area_id || "";
  const position = areaName && areaId ? `${areaName} (${areaId})` : areaId || areaName;
  const inventory =
    summary.active_actor_inventory && typeof summary.active_actor_inventory === "object"
      ? summary.active_actor_inventory
      : {};
  setPreValue(elements.flowCurrentActor, formatField(actorId || ""));
  setPreValue(
    elements.flowCurrentPosition,
    formatField(position === undefined ? "" : position)
  );
  setPreValue(elements.flowNarrative, formatField(turnData.narrative_text || ""));
  setPreValue(elements.flowObjective, formatField(summary.objective || ""));
  setPreValue(
    elements.flowAreaDescription,
    formatField(summary.active_area_description || "")
  );
  setPreValue(elements.flowInventory, formatField(inventory));
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
    return "http://127.0.0.1:8000";
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
    state.latestTurnResponse = null;
    setPreValue(elements.turnNarrative, "");
    setPreValue(elements.turnDialogType, "");
    setPreValue(elements.turnToolCalls, "");
    setPreValue(elements.turnAppliedActions, "");
    setPreValue(elements.turnToolFeedback, "");
    setPreValue(elements.turnConflictReport, "");
    setPreValue(elements.turnStateSummary, "");
    setPreValue(elements.turnGuardInsight, "");
    renderGameplaySnapshot(null);
    return;
  }
  state.latestTurnResponse = data;
  setPreValue(elements.turnNarrative, formatField(data.narrative_text));
  setPreValue(elements.turnDialogType, formatField(data.dialog_type));
  setPreValue(elements.turnToolCalls, formatField(data.tool_calls));
  setPreValue(elements.turnAppliedActions, formatField(data.applied_actions));
  setPreValue(elements.turnToolFeedback, formatField(data.tool_feedback));
  setPreValue(elements.turnConflictReport, formatField(data.conflict_report));
  setPreValue(elements.turnStateSummary, formatField(data.state_summary));
  renderActiveActorStateFromSummary(data.state_summary);
  renderGameplaySnapshot(data);

  const failedCalls =
    data.tool_feedback &&
    data.tool_feedback.failed_calls &&
    Array.isArray(data.tool_feedback.failed_calls)
      ? data.tool_feedback.failed_calls
      : [];
  const reasons = failedCalls.map((item) => item.reason).filter(Boolean);
  const insight = {
    has_conflict_report: Boolean(data.conflict_report),
    failed_call_reasons: reasons,
    repeat_illegal_request_detected: reasons.includes("repeat_illegal_request"),
    note:
      reasons.includes("repeat_illegal_request")
        ? "Backend suppressed repeated illegal request based on recent failed signatures."
        : "",
  };
  setPreValue(elements.turnGuardInsight, formatField(insight));
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
  renderErrorInspector(status, responseText);

  return { ok, status, responseText, data: safeJsonParse(responseText) };
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
    path: "/api/v1/campaign/list",
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
    path: "/api/v1/campaign/create",
    bodyText: raw,
  });
  const data = safeJsonParse(result.responseText);
  const campaignId = extractCampaignIdFromResponse(data);
  if (campaignId) {
    setCurrentCampaignId(campaignId);
  }
  return {
    ok: result.ok,
    status: result.status,
    campaign_id: campaignId || "",
    raw: result.responseText || "",
  };
}

async function selectActor() {
  const raw = elements.selectActorRaw.value;
  await sendRequest({
    method: "POST",
    path: "/api/v1/campaign/select_actor",
    bodyText: raw,
  });
}

async function sendTurn() {
  const raw = elements.turnRaw.value;
  const result = await sendRequest({
    method: "POST",
    path: "/api/v1/chat/turn",
    bodyText: raw,
  });
  renderTurnResponse(result.responseText);
  if (state.autoRefreshStatusAfterTurn) {
    await fetchCampaignStatus();
  }
  return result;
}

function getFlowRetryCount() {
  const parsed = Number(elements.flowRetryCount.value);
  if (!Number.isFinite(parsed)) {
    return 2;
  }
  const normalized = Math.round(parsed);
  if (normalized < 1) {
    return 1;
  }
  if (normalized > 5) {
    return 5;
  }
  return normalized;
}

function getPreferredMoveActorId() {
  const explicit = elements.moveActorIdInput.value.trim();
  if (explicit) {
    return explicit;
  }
  const summaryActorId =
    state.latestTurnStateSummary &&
    state.latestTurnStateSummary.active_actor_id
      ? String(state.latestTurnStateSummary.active_actor_id)
      : "";
  if (summaryActorId) {
    return summaryActorId;
  }
  const actorInput = elements.activeActorInput.value.trim();
  if (actorInput) {
    return actorInput;
  }
  return "pc_001";
}

function buildToolStepInstruction(tool, args) {
  return [
    "[UI_FLOW_STEP]",
    "Return JSON with keys assistant_text, dialog_type, tool_calls.",
    `Execute exactly one tool_call now: ${tool}.`,
    `Use args exactly: ${JSON.stringify(args)}.`,
    "Do not call any additional tools.",
    "Keep assistant_text empty.",
  ].join(" ");
}

function findAppliedActionByTool(data, expectedTool) {
  if (!data || typeof data !== "object" || !Array.isArray(data.applied_actions)) {
    return null;
  }
  return data.applied_actions.find(
    (item) => item && typeof item === "object" && item.tool === expectedTool
  );
}

function summarizeStepFailure(lastResult, expectedTool, attempts) {
  const data = lastResult && lastResult.data ? lastResult.data : null;
  const failedCalls =
    data &&
    data.tool_feedback &&
    Array.isArray(data.tool_feedback.failed_calls)
      ? data.tool_feedback.failed_calls
      : [];
  return {
    ok: false,
    expected_tool: expectedTool,
    attempts,
    status: lastResult ? lastResult.status : "NO_RESPONSE",
    failed_calls: failedCalls,
    conflict_report: data ? data.conflict_report || null : null,
    applied_actions: data ? data.applied_actions || [] : [],
    raw: lastResult ? lastResult.responseText || "" : "",
  };
}

async function runToolStep({ stepName, expectedTool, args, resultTarget }) {
  const campaignId = state.currentCampaignId || "";
  if (!campaignId) {
    const payload = { ok: false, error: "Select or create a campaign first." };
    if (resultTarget) {
      setPreValue(resultTarget, formatField(payload));
    }
    setStatus(`${stepName} blocked: no campaign selected.`);
    return payload;
  }
  const attempts = getFlowRetryCount();
  let lastResult = null;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    const body = JSON.stringify(
      {
        campaign_id: campaignId,
        user_input: buildToolStepInstruction(expectedTool, args),
      },
      null,
      2
    );
    const result = await sendRequest({
      method: "POST",
      path: "/api/v1/chat/turn",
      bodyText: body,
    });
    lastResult = result;
    renderTurnResponse(result.responseText);
    const action = result.data
      ? findAppliedActionByTool(result.data, expectedTool)
      : null;
    if (result.ok && action) {
      const payload = {
        ok: true,
        step: stepName,
        expected_tool: expectedTool,
        attempts_used: attempt,
        action,
      };
      if (resultTarget) {
        setPreValue(resultTarget, formatField(payload));
      }
      return payload;
    }
    if (attempt < attempts) {
      setStatus(
        `${stepName}: expected tool ${expectedTool} not applied (attempt ${attempt}/${attempts}), retrying...`
      );
    }
  }
  const failure = summarizeStepFailure(lastResult, expectedTool, attempts);
  if (resultTarget) {
    setPreValue(resultTarget, formatField(failure));
  }
  return failure;
}

async function runWorldGenerateStep() {
  const worldId = elements.worldIdInput.value.trim();
  if (!worldId) {
    const payload = { ok: false, error: "world_id is required." };
    setPreValue(elements.worldGenerateResult, formatField(payload));
    setStatus("World generate requires world_id.");
    return payload;
  }
  const args = {
    world_id: worldId,
    bind_to_campaign: Boolean(elements.worldBindToCampaign.checked),
  };
  return runToolStep({
    stepName: "world_generate",
    expectedTool: "world_generate",
    args,
    resultTarget: elements.worldGenerateResult,
  });
}

async function runMapGenerateStep() {
  const parentRaw = elements.mapParentAreaInput.value.trim();
  const themeRaw = elements.mapThemeInput.value.trim();
  const seedRaw = elements.mapSeedInput.value.trim();
  const parsedSize = Number(elements.mapSizeInput.value);
  const size = Number.isFinite(parsedSize) ? Math.round(parsedSize) : 3;
  const args = {
    parent_area_id: parentRaw || null,
    theme: themeRaw || "Generated",
    constraints: {
      size: Math.min(30, Math.max(1, size)),
    },
  };
  if (seedRaw) {
    args.constraints.seed = seedRaw;
  }
  return runToolStep({
    stepName: "map_generate",
    expectedTool: "map_generate",
    args,
    resultTarget: elements.mapGenerateResult,
  });
}

async function runActorSpawnStep() {
  const characterId = elements.spawnCharacterIdInput.value.trim();
  if (!characterId) {
    const payload = { ok: false, error: "character_id is required." };
    setPreValue(elements.actorSpawnResult, formatField(payload));
    setStatus("Actor spawn requires character_id.");
    return payload;
  }
  const spawnPosition = elements.spawnPositionInput.value.trim();
  const args = {
    character_id: characterId,
    bind_to_party: Boolean(elements.spawnBindToParty.checked),
  };
  if (spawnPosition) {
    args.spawn_position = spawnPosition;
  }
  return runToolStep({
    stepName: "actor_spawn",
    expectedTool: "actor_spawn",
    args,
    resultTarget: elements.actorSpawnResult,
  });
}

async function runMoveStep() {
  const toAreaId = elements.moveToAreaInput.value.trim();
  if (!toAreaId) {
    const payload = { ok: false, error: "to_area_id is required." };
    setPreValue(elements.moveResult, formatField(payload));
    setStatus("Move requires to_area_id.");
    return payload;
  }
  const args = {
    actor_id: getPreferredMoveActorId(),
    to_area_id: toAreaId,
  };
  return runToolStep({
    stepName: "move",
    expectedTool: "move",
    args,
    resultTarget: elements.moveResult,
  });
}

async function runNarrativeTurnStep() {
  const campaignId = state.currentCampaignId || "";
  if (!campaignId) {
    const payload = { ok: false, error: "Select or create a campaign first." };
    setPreValue(elements.narrativeTurnResult, formatField(payload));
    setStatus("Narrative turn blocked: no campaign selected.");
    return payload;
  }
  const userInput =
    elements.narrativeTurnInput.value.trim() ||
    "Describe the current scene without any tool call.";
  const result = await sendRequest({
    method: "POST",
    path: "/api/v1/chat/turn",
    bodyText: JSON.stringify(
      { campaign_id: campaignId, user_input: userInput },
      null,
      2
    ),
  });
  renderTurnResponse(result.responseText);
  const payload = {
    ok: result.ok,
    status: result.status,
    narrative_text:
      result.data && typeof result.data === "object"
        ? result.data.narrative_text || ""
        : "",
    applied_actions:
      result.data && typeof result.data === "object"
        ? result.data.applied_actions || []
        : [],
  };
  setPreValue(elements.narrativeTurnResult, formatField(payload));
  return payload;
}

async function runFullGameplayFlow() {
  const resultView = {};
  const createResult = await createCampaign();
  resultView.create_campaign = createResult;
  if (!createResult.ok || !createResult.campaign_id) {
    setPreValue(elements.flowResult, formatField(resultView));
    return;
  }
  const worldResult = await runWorldGenerateStep();
  resultView.world_generate = worldResult;
  if (!worldResult.ok) {
    setPreValue(elements.flowResult, formatField(resultView));
    return;
  }
  const mapResult = await runMapGenerateStep();
  resultView.map_generate = mapResult;
  if (!mapResult.ok) {
    setPreValue(elements.flowResult, formatField(resultView));
    return;
  }
  const spawnResult = await runActorSpawnStep();
  resultView.actor_spawn = spawnResult;
  if (!spawnResult.ok) {
    setPreValue(elements.flowResult, formatField(resultView));
    return;
  }
  const moveResult = await runMoveStep();
  resultView.move = moveResult;
  if (!moveResult.ok) {
    setPreValue(elements.flowResult, formatField(resultView));
    return;
  }
  const turnResult = await runNarrativeTurnStep();
  resultView.chat_turn = turnResult;
  setPreValue(elements.flowResult, formatField(resultView));
}

async function loadSchema() {
  const query = new URLSearchParams({
    campaign_id: state.currentCampaignId || "",
  });
  const result = await sendRequest({
    method: "GET",
    path: `/api/v1/settings/schema?${query.toString()}`,
  });
  const data = safeJsonParse(result.responseText);
  if (!data) {
    setPreValue(elements.settingsDefinitions, "");
    setPreValue(elements.settingsSnapshot, "");
    return;
  }
  setPreValue(elements.settingsDefinitions, formatField(data.definitions));
  setPreValue(elements.settingsSnapshot, formatField(data.snapshot));
  applySettingsFocusSnapshot(data.snapshot);
}

async function applySettings() {
  const patchRaw = elements.settingsPatchRaw.value;
  const bodyText = buildSettingsApplyBody(state.currentCampaignId, patchRaw);
  const result = await sendRequest({
    method: "POST",
    path: "/api/v1/settings/apply",
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
  applySettingsFocusSnapshot(data.snapshot);
}

async function fetchCampaignStatus() {
  const query = new URLSearchParams({
    campaign_id: state.currentCampaignId || "",
  });
  const result = await sendRequest({
    method: "GET",
    path: `/api/v1/campaign/status?${query.toString()}`,
  });
  if (result.data) {
    renderCampaignStatusPanel(result.data);
  }
}

async function advanceMilestone() {
  const body = {
    campaign_id: state.currentCampaignId || "",
    summary: elements.milestoneSummaryInput.value || "",
  };
  const result = await sendRequest({
    method: "POST",
    path: "/api/v1/campaign/milestone/advance",
    bodyText: JSON.stringify(body, null, 2),
  });
  setPreValue(elements.advanceMilestoneResult, result.responseText || "");
  if (result.ok) {
    await fetchCampaignStatus();
  }
}

async function adoptCharacterFact() {
  const characterId = elements.adoptCharacterId.value.trim();
  if (!characterId) {
    setStatus("CharacterFact adopt requires character_id.");
    return;
  }
  const acceptedBy = elements.acceptedByInput.value.trim() || "system";
  const result = await sendRequest({
    method: "POST",
    path: `/api/v1/campaigns/${encodeURIComponent(
      state.currentCampaignId || ""
    )}/characters/facts/${encodeURIComponent(characterId)}/adopt`,
    bodyText: JSON.stringify({ accepted_by: acceptedBy }, null, 2),
  });
  setPreValue(elements.adoptFactResult, result.responseText || "");
}

async function generateCharacterFacts() {
  const campaignId = state.currentCampaignId || "";
  if (!campaignId) {
    setStatus("CharacterFact generate requires a selected campaign.");
    return;
  }
  const result = await sendRequest({
    method: "POST",
    path: `/api/v1/campaigns/${encodeURIComponent(campaignId)}/characters/generate`,
    bodyText: elements.generateCharacterRaw.value,
  });
  setPreValue(elements.generateCharacterResult, result.responseText || "");
}

function inferCharacterIdFromGenerate(data) {
  if (!data || typeof data !== "object") {
    return "";
  }
  if (!Array.isArray(data.individual_paths) || !data.individual_paths.length) {
    return "";
  }
  const first = String(data.individual_paths[0] || "");
  const match = first.match(/\/([^/]+)\.fact\.draft\.json$/);
  return match ? decodeURIComponent(match[1]) : "";
}

async function runCharacterLoop() {
  const campaignId = state.currentCampaignId || "";
  if (!campaignId) {
    setStatus("Run Loop requires a selected campaign.");
    return;
  }
  const resultView = {};

  const generateResult = await sendRequest({
    method: "POST",
    path: `/api/v1/campaigns/${encodeURIComponent(campaignId)}/characters/generate`,
    bodyText: elements.generateCharacterRaw.value,
  });
  setPreValue(elements.generateCharacterResult, generateResult.responseText || "");
  resultView.generate =
    generateResult.data && typeof generateResult.data === "object"
      ? generateResult.data
      : { status: generateResult.status, raw: generateResult.responseText || "" };
  if (!generateResult.ok || !generateResult.data) {
    setPreValue(elements.runLoopResult, formatField(resultView));
    return;
  }

  const characterId =
    elements.adoptCharacterId.value.trim() ||
    inferCharacterIdFromGenerate(generateResult.data);
  if (!characterId) {
    resultView.error = "Could not infer character_id for adoption.";
    setPreValue(elements.runLoopResult, formatField(resultView));
    return;
  }
  elements.adoptCharacterId.value = characterId;

  const acceptedBy = elements.acceptedByInput.value.trim() || "system";
  const adoptResult = await sendRequest({
    method: "POST",
    path: `/api/v1/campaigns/${encodeURIComponent(
      campaignId
    )}/characters/facts/${encodeURIComponent(characterId)}/adopt`,
    bodyText: JSON.stringify({ accepted_by: acceptedBy }, null, 2),
  });
  setPreValue(elements.adoptFactResult, adoptResult.responseText || "");
  resultView.adopt =
    adoptResult.data && typeof adoptResult.data === "object"
      ? adoptResult.data
      : { status: adoptResult.status, raw: adoptResult.responseText || "" };
  if (!adoptResult.ok) {
    setPreValue(elements.runLoopResult, formatField(resultView));
    return;
  }

  const turnResult = await sendRequest({
    method: "POST",
    path: "/api/v1/chat/turn",
    bodyText: JSON.stringify(
      {
        campaign_id: campaignId,
        user_input: "Introduce yourself briefly.",
      },
      null,
      2
    ),
  });
  renderTurnResponse(turnResult.responseText);
  resultView.turn =
    turnResult.data && typeof turnResult.data === "object"
      ? turnResult.data
      : { status: turnResult.status, raw: turnResult.responseText || "" };
  resultView.turn_debug =
    turnResult.data && turnResult.data.debug ? turnResult.data.debug : null;
  if (!turnResult.ok) {
    setPreValue(elements.runLoopResult, formatField(resultView));
    return;
  }

  const query = new URLSearchParams({ campaign_id: campaignId });
  const statusResult = await sendRequest({
    method: "GET",
    path: `/api/v1/campaign/status?${query.toString()}`,
  });
  if (statusResult.data) {
    renderCampaignStatusPanel(statusResult.data);
  }
  resultView.status =
    statusResult.data && typeof statusResult.data === "object"
      ? statusResult.data
      : { status: statusResult.status, raw: statusResult.responseText || "" };

  setPreValue(elements.runLoopResult, formatField(resultView));
}

function buildFocusPatchFromToggles() {
  const patch = {};
  if (elements.toggleStrictGuard.value !== "unchanged") {
    patch["dialog.strict_semantic_guard"] =
      elements.toggleStrictGuard.value === "true";
  }
  if (elements.toggleConflictTextChecks.value !== "unchanged") {
    patch["dialog.conflict_text_checks_enabled"] =
      elements.toggleConflictTextChecks.value === "true";
  }
  if (elements.toggleCompressEnabled.value !== "unchanged") {
    const nextCompress = elements.toggleCompressEnabled.value === "true";
    patch["context.compress_enabled"] = nextCompress;
    patch["context.full_context_enabled"] = !nextCompress;
  }
  return patch;
}

async function applyFocusToggles() {
  const patch = buildFocusPatchFromToggles();
  if (!Object.keys(patch).length) {
    setStatus("No focus toggle changed.");
    return;
  }
  const result = await sendRequest({
    method: "POST",
    path: "/api/v1/settings/apply",
    bodyText: JSON.stringify(
      {
        campaign_id: state.currentCampaignId || "",
        patch,
      },
      null,
      2
    ),
  });
  setPreValue(elements.toggleApplyResult, result.responseText || "");
  if (result.data && result.data.snapshot) {
    applySettingsFocusSnapshot(result.data.snapshot);
  }
}

function toggleAutoRefreshAfterTurn() {
  state.autoRefreshStatusAfterTurn = !state.autoRefreshStatusAfterTurn;
  elements.refreshAfterTurn.textContent = `Auto Refresh After Turn: ${
    state.autoRefreshStatusAfterTurn ? "ON" : "OFF"
  }`;
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
  elements.runWorldGenerate.addEventListener("click", runWorldGenerateStep);
  elements.runMapGenerate.addEventListener("click", runMapGenerateStep);
  elements.runActorSpawn.addEventListener("click", runActorSpawnStep);
  elements.runMove.addEventListener("click", runMoveStep);
  elements.runFlowCreateCampaign.addEventListener("click", async () => {
    const result = await createCampaign();
    setPreValue(elements.flowResult, formatField({ create_campaign: result }));
  });
  elements.runFlowWorld.addEventListener("click", async () => {
    const result = await runWorldGenerateStep();
    setPreValue(elements.flowResult, formatField({ world_generate: result }));
  });
  elements.runFlowMap.addEventListener("click", async () => {
    const result = await runMapGenerateStep();
    setPreValue(elements.flowResult, formatField({ map_generate: result }));
  });
  elements.runFlowSpawn.addEventListener("click", async () => {
    const result = await runActorSpawnStep();
    setPreValue(elements.flowResult, formatField({ actor_spawn: result }));
  });
  elements.runFlowMove.addEventListener("click", async () => {
    const result = await runMoveStep();
    setPreValue(elements.flowResult, formatField({ move: result }));
  });
  elements.runFlowTurn.addEventListener("click", async () => {
    const result = await runNarrativeTurnStep();
    setPreValue(elements.flowResult, formatField({ chat_turn: result }));
  });
  elements.runFullFlow.addEventListener("click", runFullGameplayFlow);
  elements.applyActorToRaw.addEventListener("click", applyActorToRaw);
  elements.selectActorBtn.addEventListener("click", selectActor);
  elements.applyUserInput.addEventListener("click", applyUserInputToRaw);
  elements.sendTurn.addEventListener("click", sendTurn);
  elements.fetchCampaignStatus.addEventListener("click", fetchCampaignStatus);
  elements.refreshAfterTurn.addEventListener("click", toggleAutoRefreshAfterTurn);
  elements.advanceMilestoneBtn.addEventListener("click", advanceMilestone);
  elements.adoptFactBtn.addEventListener("click", adoptCharacterFact);
  elements.generateCharacterBtn.addEventListener("click", generateCharacterFacts);
  elements.runLoopBtn.addEventListener("click", runCharacterLoop);
  elements.applyFocusToggles.addEventListener("click", applyFocusToggles);
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

  elements.generateCharacterRaw.value = JSON.stringify(
    {
      language: "zh-CN",
      tone_style: ["grim", "mystery"],
      tone_vocab_only: true,
      allowed_tones: ["grim", "mystery", "low-magic"],
      party_context: [],
      constraints: {
        allowed_roles: ["scout", "guardian", "speaker"],
        style_notes: "grounded names",
      },
      count: 3,
      request_id: "req_ui_manual_001",
    },
    null,
    2
  );

  elements.settingsPatchRaw.value = '{ "dialog.auto_type_enabled": false }';
  elements.worldIdInput.value = "world_ui_flow_v1";
  elements.worldBindToCampaign.checked = true;
  elements.mapParentAreaInput.value = "area_001";
  elements.mapThemeInput.value = "UI Path";
  elements.mapSizeInput.value = "3";
  elements.mapSeedInput.value = "ui-flow";
  elements.spawnCharacterIdInput.value = "char_ui_support";
  elements.spawnPositionInput.value = "";
  elements.spawnBindToParty.checked = true;
  elements.moveActorIdInput.value = "";
  elements.moveToAreaInput.value = "area_002";
  elements.flowRetryCount.value = "2";
  elements.narrativeTurnInput.value =
    "Describe the current scene without calling tools.";
  setPreValue(
    elements.errorInspector,
    formatField({ status: "", detail: "", suggestion: "" })
  );
  setPreValue(elements.turnGuardInsight, "");
  setPreValue(elements.campaignLifecycle, "");
  setPreValue(elements.campaignMilestone, "");
  setPreValue(elements.activeActorState, "");
  setPreValue(elements.settingsFocusView, "");
  setPreValue(elements.advanceMilestoneResult, "");
  setPreValue(elements.adoptFactResult, "");
  setPreValue(elements.generateCharacterResult, "");
  setPreValue(elements.runLoopResult, "");
  setPreValue(elements.toggleApplyResult, "");
  setPreValue(elements.worldGenerateResult, "");
  setPreValue(elements.mapGenerateResult, "");
  setPreValue(elements.actorSpawnResult, "");
  setPreValue(elements.moveResult, "");
  setPreValue(elements.flowCurrentActor, "");
  setPreValue(elements.flowCurrentPosition, "");
  setPreValue(elements.flowNarrative, "");
  setPreValue(elements.flowObjective, "");
  setPreValue(elements.flowAreaDescription, "");
  setPreValue(elements.flowInventory, "");
  setPreValue(elements.narrativeTurnResult, "");
  setPreValue(elements.flowResult, "");
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
  elements.refreshAfterTurn.textContent = "Auto Refresh After Turn: OFF";
  setStatus("Ready.");
}

init();
