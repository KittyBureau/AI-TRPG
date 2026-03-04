const BASE_URL_KEY = "raw-console-base-url";

const elements = {
  statusLine: document.getElementById("statusLine"),
  baseUrlInput: document.getElementById("baseUrlInput"),
  campaignSelect: document.getElementById("campaignSelect"),
  refreshCampaignsBtn: document.getElementById("refreshCampaignsBtn"),
  actorIdsInput: document.getElementById("actorIdsInput"),
  applyActorsBtn: document.getElementById("applyActorsBtn"),
  useSnapshotActorsBtn: document.getElementById("useSnapshotActorsBtn"),
  initiativeList: document.getElementById("initiativeList"),
  failureStrategySelect: document.getElementById("failureStrategySelect"),
  runRoundBtn: document.getElementById("runRoundBtn"),
  roundLog: document.getElementById("roundLog"),
  snapshotView: document.getElementById("snapshotView"),
};

const state = {
  baseUrl: "",
  campaignId: "",
  actorIds: [],
  initiativeOrder: [],
  actionByActor: {},
  lastSummary: null,
  failureStrategy: "stop",
};

function setStatus(text) {
  elements.statusLine.textContent = text;
}

function formatJson(value) {
  return JSON.stringify(value, null, 2);
}

function normalizeBaseUrl(raw) {
  return (raw || "").trim().replace(/\/+$/, "");
}

function getBaseUrl() {
  return normalizeBaseUrl(elements.baseUrlInput.value || "");
}

function apiUrl(path) {
  const base = getBaseUrl();
  return `${base}${path}`;
}

async function sendRequest(path, options = {}) {
  const response = await fetch(apiUrl(path), options);
  const responseText = await response.text();
  let data = null;
  try {
    data = responseText ? JSON.parse(responseText) : null;
  } catch (_error) {
    data = null;
  }
  return { ok: response.ok, status: response.status, data, responseText };
}

function parseActorIds(raw) {
  const tokens = (raw || "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
  const seen = new Set();
  const ordered = [];
  for (const token of tokens) {
    if (!seen.has(token)) {
      seen.add(token);
      ordered.push(token);
    }
  }
  return ordered;
}

function ensureActionSlots() {
  for (const actorId of state.initiativeOrder) {
    if (!(actorId in state.actionByActor)) {
      state.actionByActor[actorId] = "";
    }
  }
}

function moveActor(actorId, direction) {
  const idx = state.initiativeOrder.indexOf(actorId);
  if (idx < 0) {
    return;
  }
  const next = idx + direction;
  if (next < 0 || next >= state.initiativeOrder.length) {
    return;
  }
  const swapped = [...state.initiativeOrder];
  const temp = swapped[idx];
  swapped[idx] = swapped[next];
  swapped[next] = temp;
  state.initiativeOrder = swapped;
  renderInitiativeList();
}

function renderInitiativeList() {
  ensureActionSlots();
  elements.initiativeList.innerHTML = "";
  if (!state.initiativeOrder.length) {
    const empty = document.createElement("pre");
    empty.textContent = "No actors. Add actor ids first.";
    elements.initiativeList.appendChild(empty);
    return;
  }
  state.initiativeOrder.forEach((actorId, index) => {
    const row = document.createElement("div");
    row.className = "panel";
    row.style.padding = "0.9rem";

    const header = document.createElement("div");
    header.className = "inline";
    const title = document.createElement("strong");
    title.textContent = `${index + 1}. ${actorId}`;
    const upBtn = document.createElement("button");
    upBtn.className = "ghost";
    upBtn.textContent = "Up";
    upBtn.addEventListener("click", () => moveActor(actorId, -1));
    const downBtn = document.createElement("button");
    downBtn.className = "ghost";
    downBtn.textContent = "Down";
    downBtn.addEventListener("click", () => moveActor(actorId, 1));
    header.appendChild(title);
    header.appendChild(upBtn);
    header.appendChild(downBtn);

    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.placeholder = "Action input for this actor...";
    textarea.value = state.actionByActor[actorId] || "";
    textarea.addEventListener("input", (event) => {
      state.actionByActor[actorId] = event.target.value;
    });

    row.appendChild(header);
    row.appendChild(textarea);
    elements.initiativeList.appendChild(row);
  });
}

function renderSnapshot(summary) {
  if (!summary || typeof summary !== "object") {
    elements.snapshotView.textContent = "";
    return;
  }
  const actorId = summary.active_actor_id || "";
  const payload = {
    active_actor_id: actorId,
    objective: summary.objective || "",
    active_area_id: summary.active_area_id || "",
    active_area_name: summary.active_area_name || "",
    active_area_description: summary.active_area_description || "",
    active_actor_hp: summary.hp ? summary.hp[actorId] : undefined,
    active_actor_state: summary.character_states
      ? summary.character_states[actorId]
      : undefined,
    active_actor_inventory: summary.active_actor_inventory || {},
  };
  elements.snapshotView.textContent = formatJson(payload);
}

function inventoryChanges(beforeInv, afterInv) {
  const keys = new Set([
    ...Object.keys(beforeInv || {}),
    ...Object.keys(afterInv || {}),
  ]);
  const changes = [];
  for (const key of [...keys].sort()) {
    const before = typeof beforeInv[key] === "number" ? beforeInv[key] : 0;
    const after = typeof afterInv[key] === "number" ? afterInv[key] : 0;
    if (before !== after) {
      changes.push({
        item_id: key,
        before,
        after,
        delta: after - before,
      });
    }
  }
  return changes;
}

function actorValue(summary, mapKey, actorId) {
  if (!summary || typeof summary !== "object") {
    return null;
  }
  const group = summary[mapKey];
  if (!group || typeof group !== "object") {
    return null;
  }
  if (!(actorId in group)) {
    return null;
  }
  return group[actorId];
}

function actorInventory(summary, actorId) {
  if (!summary || typeof summary !== "object") {
    return {};
  }
  const all = summary.inventories;
  if (!all || typeof all !== "object") {
    return {};
  }
  const value = all[actorId];
  if (!value || typeof value !== "object") {
    return {};
  }
  return value;
}

function buildDelta(prevSummary, nextSummary, actorId) {
  const beforePosition = actorValue(prevSummary, "positions", actorId);
  const afterPosition = actorValue(nextSummary, "positions", actorId);
  const beforeHp = actorValue(prevSummary, "hp", actorId);
  const afterHp = actorValue(nextSummary, "hp", actorId);
  const beforeState = actorValue(prevSummary, "character_states", actorId);
  const afterState = actorValue(nextSummary, "character_states", actorId);
  const beforeInventory = actorInventory(prevSummary, actorId);
  const afterInventory = actorInventory(nextSummary, actorId);
  const invChanges = inventoryChanges(beforeInventory, afterInventory);

  const delta = {
    actor_id: actorId,
    changed: false,
    position: {
      before: beforePosition,
      after: afterPosition,
      changed: beforePosition !== afterPosition,
    },
    hp: {
      before: beforeHp,
      after: afterHp,
      changed: beforeHp !== afterHp,
    },
    character_state: {
      before: beforeState,
      after: afterState,
      changed: beforeState !== afterState,
    },
    inventory: {
      before: beforeInventory,
      after: afterInventory,
      changed: invChanges.length > 0,
      changes: invChanges,
    },
    error: null,
  };
  delta.changed =
    delta.position.changed ||
    delta.hp.changed ||
    delta.character_state.changed ||
    delta.inventory.changed;
  return delta;
}

function buildErrorDelta(prevSummary, actorId, errorType, message, statusCode = null) {
  const delta = buildDelta(prevSummary, prevSummary, actorId);
  delta.error = {
    type: errorType,
    status: statusCode,
    message,
  };
  return delta;
}

function appendRoundLog(entry) {
  const block = document.createElement("div");
  block.className = "panel";
  block.style.padding = "0.9rem";

  const title = document.createElement("h3");
  title.textContent = `${entry.actorId} (${entry.dialogType || "scene_description"})`;
  const narrative = document.createElement("pre");
  narrative.textContent = entry.narrativeText || "(empty)";
  const delta = document.createElement("pre");
  delta.textContent = formatJson(entry.delta);

  block.appendChild(title);
  block.appendChild(narrative);
  block.appendChild(delta);
  elements.roundLog.appendChild(block);
}

async function refreshCampaigns() {
  const result = await sendRequest("/api/v1/campaign/list");
  if (!result.ok || !result.data || !Array.isArray(result.data.campaigns)) {
    setStatus(`Failed to load campaigns (${result.status}).`);
    return;
  }
  elements.campaignSelect.innerHTML = "";
  for (const campaign of result.data.campaigns) {
    const option = document.createElement("option");
    option.value = campaign.id;
    option.textContent = `${campaign.id} (active=${campaign.active_actor_id})`;
    elements.campaignSelect.appendChild(option);
  }
  const selected = elements.campaignSelect.value || "";
  state.campaignId = selected;
  setStatus(`Loaded ${result.data.campaigns.length} campaigns.`);
}

function applyActorsFromInput() {
  const actorIds = parseActorIds(elements.actorIdsInput.value);
  state.actorIds = actorIds;
  state.initiativeOrder = [...actorIds];
  ensureActionSlots();
  renderInitiativeList();
  setStatus(`Loaded ${actorIds.length} actor slots.`);
}

function applyActorsFromSnapshot() {
  if (!state.lastSummary || !state.lastSummary.positions) {
    setStatus("No snapshot positions available yet.");
    return;
  }
  const actorIds = Object.keys(state.lastSummary.positions).sort();
  elements.actorIdsInput.value = actorIds.join(", ");
  applyActorsFromInput();
}

async function runRound() {
  state.campaignId = elements.campaignSelect.value || "";
  state.failureStrategy = elements.failureStrategySelect.value || "stop";
  if (!state.campaignId) {
    setStatus("Select a campaign first.");
    return;
  }
  if (!state.initiativeOrder.length) {
    setStatus("Add actor ids first.");
    return;
  }
  elements.roundLog.innerHTML = "";
  for (const actorId of state.initiativeOrder) {
    const userInput = (state.actionByActor[actorId] || "").trim();
    if (!userInput) {
      const skippedDelta = buildErrorDelta(
        state.lastSummary,
        actorId,
        "skipped",
        "No action input provided.",
        null
      );
      appendRoundLog({
        actorId,
        dialogType: "skipped",
        narrativeText: "No action input provided.",
        delta: skippedDelta,
      });
      continue;
    }
    const result = await sendRequest("/api/v1/chat/turn", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        campaign_id: state.campaignId,
        user_input: userInput,
        execution: { actor_id: actorId },
      }),
    });
    if (!result.ok || !result.data) {
      const errorDelta = buildErrorDelta(
        state.lastSummary,
        actorId,
        "request_failed",
        result.responseText || `HTTP ${result.status}`,
        result.status
      );
      appendRoundLog({
        actorId,
        dialogType: "error",
        narrativeText: result.responseText || `HTTP ${result.status}`,
        delta: errorDelta,
      });
      if (state.failureStrategy === "stop") {
        setStatus(`Round stopped on ${actorId} (HTTP ${result.status}).`);
        return;
      }
      setStatus(
        `Round continued after ${actorId} failure (HTTP ${result.status}).`
      );
      continue;
    }
    const payload = result.data;
    const nextSummary = payload.state_summary || null;
    if (payload.effective_actor_id !== actorId) {
      const mismatchDelta = buildErrorDelta(
        state.lastSummary,
        actorId,
        "actor_context_mismatch",
        `expected=${actorId}, got=${String(payload.effective_actor_id)}`,
        result.status
      );
      appendRoundLog({
        actorId,
        dialogType: "error",
        narrativeText: "Turn response actor mismatch.",
        delta: mismatchDelta,
      });
      if (state.failureStrategy === "stop") {
        setStatus(`Round stopped on ${actorId} (effective_actor mismatch).`);
        return;
      }
      setStatus(`Round continued after ${actorId} actor mismatch.`);
      continue;
    }
    const delta = buildDelta(state.lastSummary, nextSummary, actorId);
    appendRoundLog({
      actorId,
      dialogType: payload.dialog_type,
      narrativeText: payload.narrative_text,
      delta,
    });
    state.lastSummary = nextSummary;
    renderSnapshot(state.lastSummary);
  }
  setStatus("Round complete.");
}

function bindEvents() {
  elements.baseUrlInput.addEventListener("change", () => {
    const normalized = getBaseUrl();
    localStorage.setItem(BASE_URL_KEY, normalized);
    setStatus(`Base URL set to ${normalized || "(same origin)"}.`);
  });
  elements.refreshCampaignsBtn.addEventListener("click", refreshCampaigns);
  elements.campaignSelect.addEventListener("change", () => {
    state.campaignId = elements.campaignSelect.value || "";
  });
  elements.applyActorsBtn.addEventListener("click", applyActorsFromInput);
  elements.useSnapshotActorsBtn.addEventListener("click", applyActorsFromSnapshot);
  elements.failureStrategySelect.addEventListener("change", () => {
    state.failureStrategy = elements.failureStrategySelect.value || "stop";
  });
  elements.runRoundBtn.addEventListener("click", runRound);
}

async function init() {
  elements.baseUrlInput.value = localStorage.getItem(BASE_URL_KEY) || "";
  bindEvents();
  elements.failureStrategySelect.value = state.failureStrategy;
  renderInitiativeList();
  renderSnapshot(null);
  await refreshCampaigns();
}

init();
