import {
  createCharacter as createCharacterApi,
  getCampaign as getCampaignApi,
  getRuntimeStatus as getRuntimeStatusApi,
  listCampaigns as listCampaignsApi,
  listCharacters,
  loadCharacterToCampaign as loadCharacterToCampaignApi,
  selectActor as selectActorApi,
} from "../api/api.js";

const BASE_URL_KEY = "raw-console-base-url";
const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";

const state = {
  baseUrl: "",
  statusMessage: "Idle",
  campaignId: null,
  campaign: {
    party_character_ids: [],
    active_actor_id: "",
    status: null,
  },
  character: {
    library: [],
    selected_character_id: null,
    create_form: {
      name: "",
      summary: "",
      tags: "",
    },
    status: "idle",
    error: null,
  },
  campaignOptions: [],
  initiativeOrder: [],
  plannedActions: {},
  actionInputs: {},
  failurePolicy: "stop",
  roundState: "idle",
  roundNumber: 0,
  stateSummary: null,
  inventoryByActor: {},
  selectedItemIdByActor: {},
  mapView: null,
  turnHistory: [],
  debug: {
    requestText: "",
    responseText: "",
    traces: [],
  },
  backend: {
    ready: null,
    reason: "unknown",
  },
};

const subscribers = new Set();

function emit() {
  for (const subscriber of subscribers) {
    subscriber(getState());
  }
}

function normalizeBaseUrl(raw) {
  const normalized = (raw || "").trim().replace(/\/+$/, "");
  return normalized || DEFAULT_BACKEND_BASE_URL;
}

function syncCampaignOption(campaignId, patch = {}) {
  if (!campaignId) {
    return;
  }
  const index = state.campaignOptions.findIndex((campaign) => campaign.id === campaignId);
  if (index < 0) {
    return;
  }
  const current =
    state.campaignOptions[index] && typeof state.campaignOptions[index] === "object"
      ? state.campaignOptions[index]
      : {};
  state.campaignOptions[index] = {
    ...current,
    ...patch,
  };
}

function hasOwn(object, key) {
  return Object.prototype.hasOwnProperty.call(object, key);
}

function normalizeActorId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizeItemId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizeInventory(rawInventory) {
  const normalized = {};
  if (!rawInventory || typeof rawInventory !== "object" || Array.isArray(rawInventory)) {
    return normalized;
  }
  for (const [rawItemId, rawQuantity] of Object.entries(rawInventory)) {
    const itemId = normalizeItemId(rawItemId);
    const quantity = Number(rawQuantity);
    if (!itemId || !Number.isInteger(quantity) || quantity <= 0) {
      continue;
    }
    normalized[itemId] = quantity;
  }
  return normalized;
}

function normalizeInventoriesByActor(rawInventories) {
  const normalized = {};
  if (!rawInventories || typeof rawInventories !== "object" || Array.isArray(rawInventories)) {
    return normalized;
  }
  for (const [rawActorId, rawInventory] of Object.entries(rawInventories)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      continue;
    }
    normalized[actorId] = normalizeInventory(rawInventory);
  }
  return normalized;
}

function reconcileSelectedItemsWithInventory() {
  let changed = false;
  const nextSelections = {
    ...state.selectedItemIdByActor,
  };
  for (const [rawActorId, rawItemId] of Object.entries(nextSelections)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      delete nextSelections[rawActorId];
      changed = true;
      continue;
    }
    const itemId = normalizeItemId(rawItemId);
    if (!itemId) {
      if (nextSelections[actorId] !== null) {
        nextSelections[actorId] = null;
        changed = true;
      }
      continue;
    }
    if (
      hasOwn(state.inventoryByActor, actorId) &&
      !hasOwn(state.inventoryByActor[actorId], itemId)
    ) {
      nextSelections[actorId] = null;
      changed = true;
    }
  }
  if (changed) {
    state.selectedItemIdByActor = nextSelections;
  }
  return changed;
}

function replaceInventoryByActor(rawInventories) {
  state.inventoryByActor = normalizeInventoriesByActor(rawInventories);
  reconcileSelectedItemsWithInventory();
}

function patchInventoryForActor(actorId, rawInventory) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return;
  }
  state.inventoryByActor = {
    ...state.inventoryByActor,
    [normalizedActorId]: normalizeInventory(rawInventory),
  };
  reconcileSelectedItemsWithInventory();
}

function applyPartyActorsToState(actorIds) {
  const normalized = Array.isArray(actorIds)
    ? actorIds
        .filter((value) => typeof value === "string" && value.trim())
        .map((value) => value.trim())
    : [];
  state.campaign.party_character_ids = [...new Set(normalized)];
  state.initiativeOrder = [...state.campaign.party_character_ids];
  const nextPlannedActions = {};
  for (const actorId of state.initiativeOrder) {
    const existing = state.plannedActions[actorId];
    nextPlannedActions[actorId] = Array.isArray(existing) ? existing : [];
  }
  state.plannedActions = nextPlannedActions;
  const nextInputs = {};
  for (const actorId of state.initiativeOrder) {
    nextInputs[actorId] = state.actionInputs[actorId] || "";
  }
  state.actionInputs = nextInputs;
}

function withEmit(emitChange = true) {
  if (emitChange) {
    emit();
  }
}

export function getState() {
  return state;
}

export function subscribe(subscriber) {
  subscribers.add(subscriber);
  return () => subscribers.delete(subscriber);
}

export function initializeStore() {
  state.baseUrl = normalizeBaseUrl(localStorage.getItem(BASE_URL_KEY) || "");
  emit();
}

export function setStatusMessage(message) {
  state.statusMessage = typeof message === "string" && message.trim() ? message.trim() : "Idle";
  emit();
}

export function setBaseUrl(value) {
  state.baseUrl = normalizeBaseUrl(value);
  localStorage.setItem(BASE_URL_KEY, state.baseUrl);
  emit();
}

export function setCampaignOptions(campaigns) {
  state.campaignOptions = Array.isArray(campaigns) ? campaigns : [];
  if (!state.campaignId && state.campaignOptions.length > 0) {
    state.campaignId = state.campaignOptions[0].id;
  }
  const selectedCampaign = state.campaignOptions.find(
    (campaign) => campaign.id === state.campaignId
  );
  if (
    selectedCampaign &&
    typeof selectedCampaign.active_actor_id === "string"
  ) {
    state.campaign.active_actor_id = selectedCampaign.active_actor_id;
  }
  emit();
}

export function setCampaignId(campaignId) {
  const previousCampaignId = state.campaignId;
  state.campaignId = campaignId || null;
  const selectedCampaign = state.campaignOptions.find(
    (campaign) => campaign.id === state.campaignId
  );
  if (
    selectedCampaign &&
    typeof selectedCampaign.active_actor_id === "string"
  ) {
    state.campaign.active_actor_id = selectedCampaign.active_actor_id;
  }
  if (previousCampaignId !== state.campaignId) {
    state.campaign.status = null;
  }
  emit();
}

export function setPartyActors(actorIds) {
  applyPartyActorsToState(actorIds);
  emit();
}

export function setSelectedItemForActor(actorId, itemId) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return false;
  }
  const normalizedItemId = normalizeItemId(itemId);
  if (!normalizedItemId) {
    state.selectedItemIdByActor = {
      ...state.selectedItemIdByActor,
      [normalizedActorId]: null,
    };
    emit();
    return true;
  }
  const inventory = state.inventoryByActor[normalizedActorId];
  if (!inventory || !hasOwn(inventory, normalizedItemId)) {
    return false;
  }
  const currentItemId = normalizeItemId(state.selectedItemIdByActor[normalizedActorId]);
  state.selectedItemIdByActor = {
    ...state.selectedItemIdByActor,
    [normalizedActorId]: currentItemId === normalizedItemId ? null : normalizedItemId,
  };
  emit();
  return true;
}

export function setCharacterCreateForm(nextForm) {
  const patch =
    nextForm && typeof nextForm === "object" && !Array.isArray(nextForm)
      ? nextForm
      : {};
  state.character.create_form = {
    ...state.character.create_form,
    ...patch,
  };
  emit();
}

export function setCharacterSelectedId(characterId) {
  state.character.selected_character_id =
    typeof characterId === "string" && characterId.trim()
      ? characterId.trim()
      : null;
  emit();
}

function parseTagsInput(tags) {
  if (!tags || typeof tags !== "string") {
    return [];
  }
  return [...new Set(tags.split(/[\n,]/).map((item) => item.trim()).filter(Boolean))];
}

function parseApiError(result) {
  if (result?.data && typeof result.data.detail === "string") {
    return result.data.detail;
  }
  if (typeof result?.text === "string" && result.text.trim()) {
    return result.text.trim();
  }
  return `HTTP ${result?.status ?? 500}`;
}

function normalizeCampaignGetPayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return null;
  }
  const campaignId =
    typeof payload.campaign_id === "string" && payload.campaign_id.trim()
      ? payload.campaign_id.trim()
      : "";
  const selected =
    payload.selected && typeof payload.selected === "object" && !Array.isArray(payload.selected)
      ? payload.selected
      : null;
  const activeActorId =
    typeof selected?.active_actor_id === "string" ? selected.active_actor_id.trim() : "";
  if (!campaignId || !selected || !Array.isArray(selected.party_character_ids)) {
    return null;
  }
  if (!Array.isArray(payload.actors)) {
    return null;
  }
  const rawStatus =
    payload.status && typeof payload.status === "object" && !Array.isArray(payload.status)
      ? payload.status
      : null;
  const rawMilestone =
    rawStatus?.milestone &&
    typeof rawStatus.milestone === "object" &&
    !Array.isArray(rawStatus.milestone)
      ? rawStatus.milestone
      : null;
  const milestoneCurrent =
    typeof rawMilestone?.current === "string" && rawMilestone.current.trim()
      ? rawMilestone.current.trim()
      : "";
  return {
    campaignId,
    activeActorId,
    normalizedParty: [
      ...new Set(
        selected.party_character_ids
          .filter((value) => typeof value === "string" && value.trim())
          .map((value) => value.trim())
      ),
    ],
    statusSnapshot:
      rawStatus && milestoneCurrent
        ? {
            ended: rawStatus.ended === true,
            reason:
              typeof rawStatus.reason === "string" && rawStatus.reason.trim()
                ? rawStatus.reason.trim()
                : null,
            ended_at:
              typeof rawStatus.ended_at === "string" && rawStatus.ended_at.trim()
                ? rawStatus.ended_at.trim()
                : null,
            milestone: {
              current: milestoneCurrent,
              last_advanced_turn: Number.isInteger(rawMilestone.last_advanced_turn)
                ? rawMilestone.last_advanced_turn
                : 0,
              turn_trigger_interval: Number.isInteger(rawMilestone.turn_trigger_interval)
                ? rawMilestone.turn_trigger_interval
                : 0,
              pressure: Number.isInteger(rawMilestone.pressure) ? rawMilestone.pressure : 0,
              pressure_threshold: Number.isInteger(rawMilestone.pressure_threshold)
                ? rawMilestone.pressure_threshold
                : 0,
              summary: typeof rawMilestone.summary === "string" ? rawMilestone.summary.trim() : "",
            },
          }
        : null,
  };
}

function _setStatusMessageSilently(nextMessage) {
  if (typeof nextMessage !== "string" || !nextMessage.trim()) {
    return false;
  }
  if (state.statusMessage === nextMessage.trim()) {
    return false;
  }
  state.statusMessage = nextMessage.trim();
  return true;
}

function formatBackendNotReadyMessage(reason) {
  const normalized = typeof reason === "string" ? reason.trim() : "";
  if (normalized === "config_missing") {
    return "Backend credentials are not ready. Create storage/config/llm_config.json first.";
  }
  if (normalized === "keyring_missing") {
    return "Backend keyring is missing. Create storage/secrets/keyring.json before sending turns.";
  }
  if (normalized === "credentials_unavailable") {
    return "Backend credentials are not ready. Check storage/config/llm_config.json and storage/secrets/keyring.json.";
  }
  if (normalized === "keyring_locked" || normalized === "passphrase_required") {
    return "Backend is not ready yet. Run `python -m backend.tools.unlock_keyring` in a local terminal, then retry.";
  }
  return "Backend is not ready yet. Check backend runtime status and unlock the keyring locally if needed.";
}

export async function loadCharacterLibrary(baseUrl = state.baseUrl) {
  state.character.status = "loading";
  state.character.error = null;
  emit();
  const result = await listCharacters(baseUrl);
  if (!result.ok || !Array.isArray(result.data)) {
    state.character.status = "error";
    state.character.error = parseApiError(result);
    emit();
    return result;
  }
  state.character.library = result.data;
  state.character.status = "idle";
  state.character.error = null;
  emit();
  return result;
}

export async function loadCampaignOptionsFromBackend(
  baseUrl = state.baseUrl,
  options = {}
) {
  if (typeof baseUrl !== "string" || !baseUrl.trim()) {
    if (options.silent !== true) {
      state.statusMessage = "Base URL is required.";
      emit();
    }
    return {
      ok: false,
      status: 0,
      data: null,
      text: "Base URL is required.",
    };
  }
  const result = await listCampaignsApi(baseUrl);
  if (!result.ok || !result.data || !Array.isArray(result.data.campaigns)) {
    if (options.silent !== true) {
      state.statusMessage = `Failed to load campaigns (${result.status}).`;
      emit();
    }
    return result;
  }
  state.campaignOptions = result.data.campaigns;
  if (!state.campaignId && state.campaignOptions.length > 0) {
    state.campaignId = state.campaignOptions[0].id;
  }
  const selectedCampaign = state.campaignOptions.find(
    (campaign) => campaign.id === state.campaignId
  );
  if (
    selectedCampaign &&
    typeof selectedCampaign.active_actor_id === "string"
  ) {
    state.campaign.active_actor_id = selectedCampaign.active_actor_id;
  }
  if (options.silent !== true) {
    state.statusMessage = `Loaded ${result.data.campaigns.length} campaigns.`;
  }
  emit();
  return result;
}

export async function checkBackendReady(
  baseUrl = state.baseUrl,
  options = {}
) {
  if (typeof baseUrl !== "string" || !baseUrl.trim()) {
    const previousReady = state.backend.ready;
    const previousReason = state.backend.reason;
    state.backend.ready = null;
    state.backend.reason = "base_url_missing";
    let changed =
      previousReady !== state.backend.ready ||
      previousReason !== state.backend.reason;
    if (options.silent !== true && options.reportMissingBaseUrl === true) {
      changed = _setStatusMessageSilently("Base URL is required.") || changed;
    }
    if (changed) {
      emit();
    }
    return {
      ready: null,
      reason: "base_url_missing",
      ok: false,
      status: 0,
    };
  }
  const result = await getRuntimeStatusApi(baseUrl);
  if (!result.ok || !result.data || typeof result.data.ready !== "boolean") {
    const previousReady = state.backend.ready;
    const previousReason = state.backend.reason;
    state.backend.ready = null;
    state.backend.reason = "status_unavailable";
    let changed =
      previousReady !== state.backend.ready ||
      previousReason !== state.backend.reason;
    if (options.silent !== true) {
      changed =
        _setStatusMessageSilently(
          `Backend status check failed: ${parseApiError(result)}`
        ) || changed;
    }
    if (changed) {
      emit();
    }
    return {
      ready: null,
      reason: "status_unavailable",
      ok: false,
      status: result.status,
    };
  }

  const previousReady = state.backend.ready;
  const previousReason = state.backend.reason;
  state.backend.ready = result.data.ready;
  state.backend.reason =
    typeof result.data.reason === "string" && result.data.reason.trim()
      ? result.data.reason.trim()
      : "unknown";
  let changed =
    previousReady !== state.backend.ready ||
    previousReason !== state.backend.reason;
  if (!result.data.ready && options.silent !== true) {
    changed =
      _setStatusMessageSilently(
        formatBackendNotReadyMessage(state.backend.reason)
      ) || changed;
  }
  if (changed) {
    emit();
  }
  return {
    ready: state.backend.ready,
    reason: state.backend.reason,
    ok: true,
    status: result.status,
  };
}

export async function recoverFrontendSession(
  baseUrl = state.baseUrl,
  options = {}
) {
  const readiness = await checkBackendReady(baseUrl, {
    silent: options.silent !== false,
  });
  if (readiness.ready !== true) {
    return {
      ok: false,
      ready: readiness.ready,
      reason: readiness.reason,
      recovered: false,
    };
  }

  const campaignsResult = await loadCampaignOptionsFromBackend(baseUrl, {
    silent: true,
  });
  if (!campaignsResult.ok) {
    return {
      ok: false,
      ready: true,
      reason: "campaign_list_failed",
      recovered: false,
    };
  }

  const nextState = getState();
  if (nextState.campaignId) {
    const refreshResult = await refreshCampaign(nextState.campaignId, baseUrl);
    if (!refreshResult.ok) {
      return {
        ok: false,
        ready: true,
        reason: "campaign_refresh_failed",
        recovered: false,
      };
    }
  }

  if (options.loadCharacterLibrary === true) {
    await loadCharacterLibrary(baseUrl);
  }

  return {
    ok: true,
    ready: true,
    reason: "ready",
    recovered: true,
  };
}

export async function createCharacter(baseUrl = state.baseUrl, payload = null) {
  state.character.status = "creating";
  state.character.error = null;
  emit();
  const fallbackPayload = {
    name: state.character.create_form.name || "",
    summary: state.character.create_form.summary || "",
    tags: parseTagsInput(state.character.create_form.tags || ""),
  };
  const requestPayload = payload && typeof payload === "object" ? payload : fallbackPayload;
  const result = await createCharacterApi(baseUrl, requestPayload);
  if (!result.ok || !result.data || typeof result.data.character_id !== "string") {
    state.character.status = "error";
    state.character.error = parseApiError(result);
    emit();
    return result;
  }
  state.character.selected_character_id = result.data.character_id;
  state.character.status = "idle";
  state.character.error = null;
  emit();
  return result;
}

export async function loadCharacterToCampaign(
  campaignId = state.campaignId,
  characterId,
  baseUrl = state.baseUrl
) {
  state.character.status = "loading_to_campaign";
  state.character.error = null;
  emit();
  const result = await loadCharacterToCampaignApi(baseUrl, campaignId, characterId);
  if (!result.ok || !result.data) {
    state.character.status = "error";
    state.character.error = parseApiError(result);
    emit();
    return result;
  }
  if (Array.isArray(result.data.party_character_ids)) {
    applyPartyActorsToState(result.data.party_character_ids);
  }
  if (typeof result.data.active_actor_id === "string") {
    state.campaign.active_actor_id = result.data.active_actor_id;
    syncCampaignOption(campaignId, { active_actor_id: result.data.active_actor_id });
  }
  if (typeof result.data.character_id === "string") {
    state.character.selected_character_id = result.data.character_id;
  }
  state.character.status = "idle";
  state.character.error = null;
  emit();
  const refreshResult = await refreshCampaign(campaignId, baseUrl);
  if (!refreshResult.ok) {
    state.statusMessage = `Loaded character, but refresh failed: ${parseApiError(refreshResult)}`;
    emit();
  }
  return result;
}

export async function selectActiveActor(
  activeActorId,
  campaignId = state.campaignId,
  baseUrl = state.baseUrl
) {
  const normalizedActorId =
    typeof activeActorId === "string" ? activeActorId.trim() : "";
  if (!campaignId) {
    const message = "campaign_id is required";
    state.statusMessage = message;
    emit();
    return {
      ok: false,
      status: 400,
      data: { detail: message },
      text: message,
    };
  }
  if (!normalizedActorId) {
    const message = "active_actor_id is required";
    state.statusMessage = message;
    emit();
    return {
      ok: false,
      status: 400,
      data: { detail: message },
      text: message,
    };
  }

  const result = await selectActorApi(baseUrl, campaignId, normalizedActorId);
  if (!result.ok || !result.data) {
    state.statusMessage = `Set active actor failed: ${parseApiError(result)}`;
    emit();
    return result;
  }

  state.campaign.active_actor_id = normalizedActorId;
  syncCampaignOption(campaignId, { active_actor_id: normalizedActorId });
  state.statusMessage = `Active actor set to ${normalizedActorId}.`;
  emit();
  const refreshResult = await refreshCampaign(campaignId, baseUrl);
  if (!refreshResult.ok) {
    state.statusMessage = `Active actor set, but refresh failed: ${parseApiError(refreshResult)}`;
    emit();
  }
  return result;
}

export async function refreshCampaign(
  campaignId = state.campaignId,
  baseUrl = state.baseUrl
) {
  const resolvedCampaignId =
    typeof campaignId === "string" && campaignId.trim() ? campaignId.trim() : "";
  if (!resolvedCampaignId) {
    const message = "campaign_id is required";
    state.statusMessage = message;
    emit();
    return {
      ok: false,
      status: 400,
      data: { detail: message },
      text: message,
    };
  }

  const result = await getCampaignApi(baseUrl, resolvedCampaignId);
  if (!result.ok || !result.data) {
    state.campaign.status = null;
    state.statusMessage = `Refresh campaign failed: ${parseApiError(result)}`;
    emit();
    return result;
  }

  const normalizedPayload = normalizeCampaignGetPayload(result.data);
  if (!normalizedPayload) {
    const invalidResult = {
      ok: false,
      status: result.status || 500,
      data: { detail: "campaign/get returned invalid payload" },
      text: result.text,
    };
    state.campaign.status = null;
    state.statusMessage = `Refresh campaign failed: ${parseApiError(invalidResult)}`;
    emit();
    return invalidResult;
  }

  applyPartyActorsToState(normalizedPayload.normalizedParty);
  state.campaignId = normalizedPayload.campaignId;
  state.campaign.active_actor_id = normalizedPayload.activeActorId;
  state.campaign.status = normalizedPayload.statusSnapshot;
  syncCampaignOption(normalizedPayload.campaignId, {
    active_actor_id: normalizedPayload.activeActorId,
  });
  reconcileSelectedItemsWithInventory();
  state.statusMessage = `Campaign refreshed from backend: active=${state.campaign.active_actor_id || "none"}, party=${state.campaign.party_character_ids.length}.`;
  emit();
  return result;
}

export function recordTurnResult(responseData, rawText = "") {
  const payload =
    responseData && typeof responseData === "object" && !Array.isArray(responseData)
      ? responseData
      : null;
  const effectiveActorId =
    typeof payload?.effective_actor_id === "string" ? payload.effective_actor_id.trim() : "";
  if (payload?.state_summary && typeof payload.state_summary === "object") {
    state.stateSummary = payload.state_summary;
    if (payload.state_summary.inventories && typeof payload.state_summary.inventories === "object") {
      replaceInventoryByActor(payload.state_summary.inventories);
    } else if (effectiveActorId && payload.state_summary.active_actor_inventory) {
      patchInventoryForActor(effectiveActorId, payload.state_summary.active_actor_inventory);
    }
  }
  if (typeof rawText === "string") {
    state.debug.responseText = rawText;
  }
  if (effectiveActorId) {
    state.campaign.active_actor_id = effectiveActorId;
    syncCampaignOption(state.campaignId, { active_actor_id: effectiveActorId });
  }
  state.turnHistory.push({
    effective_actor_id: effectiveActorId,
    applied_actions: Array.isArray(payload?.applied_actions) ? payload.applied_actions : [],
    tool_feedback:
      payload?.tool_feedback && typeof payload.tool_feedback === "object"
        ? payload.tool_feedback
        : null,
    state_summary:
      payload?.state_summary && typeof payload.state_summary === "object"
        ? payload.state_summary
        : null,
    raw: payload,
  });
  emit();
}

export function setInitiativeOrder(order) {
  if (!Array.isArray(order)) {
    return;
  }
  state.initiativeOrder = order
    .filter((value) => typeof value === "string" && value.trim())
    .map((value) => value.trim());
  const nextPlannedActions = {};
  for (const actorId of state.initiativeOrder) {
    const existing = state.plannedActions[actorId];
    nextPlannedActions[actorId] = Array.isArray(existing) ? existing : [];
  }
  state.plannedActions = nextPlannedActions;
  const nextInputs = {};
  for (const actorId of state.initiativeOrder) {
    nextInputs[actorId] = state.actionInputs[actorId] || "";
  }
  state.actionInputs = nextInputs;
  emit();
}

export function setActionInput(actorId, value, options = {}) {
  if (!actorId) {
    return;
  }
  state.actionInputs[actorId] = typeof value === "string" ? value : "";
  withEmit(options.emit !== false);
}

function normalizeActionEnvelope(envelope) {
  if (!envelope || typeof envelope !== "object") {
    return null;
  }
  if (typeof envelope.type !== "string") {
    return null;
  }
  const type = envelope.type.trim();
  if (!type) {
    return null;
  }
  if (typeof envelope.actor_id !== "string" || !envelope.actor_id.trim()) {
    return null;
  }
  const actorId = envelope.actor_id.trim();
  if (type === "move") {
    if (typeof envelope.to_area_id !== "string" || !envelope.to_area_id.trim()) {
      return null;
    }
    return {
      type: "move",
      actor_id: actorId,
      to_area_id: envelope.to_area_id.trim(),
      to_area_name:
        typeof envelope.to_area_name === "string" ? envelope.to_area_name.trim() : "",
    };
  }
  if (type === "scene_action") {
    if (typeof envelope.action !== "string" || !envelope.action.trim()) {
      return null;
    }
    if (typeof envelope.target_id !== "string" || !envelope.target_id.trim()) {
      return null;
    }
    const params =
      envelope.params && typeof envelope.params === "object" && !Array.isArray(envelope.params)
        ? envelope.params
        : {};
    return {
      type: "scene_action",
      actor_id: actorId,
      action: envelope.action.trim(),
      target_id: envelope.target_id.trim(),
      target_label:
        typeof envelope.target_label === "string" ? envelope.target_label.trim() : "",
      params,
    };
  }
  return null;
}

export function addPlannedAction(envelope) {
  const normalized = normalizeActionEnvelope(envelope);
  if (!normalized) {
    return false;
  }
  const actorId = normalized.actor_id;
  if (!state.plannedActions[actorId]) {
    state.plannedActions[actorId] = [];
  }
  state.plannedActions[actorId].push(normalized);
  emit();
  return true;
}

export function removePlannedAction(actorId, index) {
  const list = state.plannedActions[actorId];
  if (!Array.isArray(list)) {
    return;
  }
  if (!Number.isInteger(index) || index < 0 || index >= list.length) {
    return;
  }
  list.splice(index, 1);
  emit();
}

export function clearPlannedActions(actorId = null) {
  if (actorId && state.plannedActions[actorId]) {
    state.plannedActions[actorId] = [];
    emit();
    return;
  }
  for (const key of Object.keys(state.plannedActions)) {
    state.plannedActions[key] = [];
  }
  emit();
}

export function setFailurePolicy(value) {
  state.failurePolicy = value === "continue" ? "continue" : "stop";
  emit();
}

export function setRoundState(value) {
  state.roundState = value;
  emit();
}

export function beginRound() {
  state.roundNumber += 1;
  state.roundState = "running";
  state.turnHistory = [];
  emit();
  return state.roundNumber;
}

export function finishRound() {
  state.roundState = "idle";
  emit();
}

export function appendTurnHistory(entry) {
  state.turnHistory.push(entry);
  emit();
}

export function setStateSummary(summary) {
  state.stateSummary = summary;
  emit();
}

export function setMapView(mapView) {
  state.mapView = mapView;
  emit();
}

export function setDebugRequestText(value, options = {}) {
  state.debug.requestText = typeof value === "string" ? value : "";
  withEmit(options.emit !== false);
}

export function setDebugResponseText(value) {
  state.debug.responseText = typeof value === "string" ? value : "";
  emit();
}

export function appendDebugTrace(trace) {
  state.debug.traces.push(trace);
  emit();
}

export function clearDebugTrace() {
  state.debug.traces = [];
  emit();
}

export function copyStateSnapshot() {
  return JSON.parse(JSON.stringify(state));
}

export { formatBackendNotReadyMessage };
