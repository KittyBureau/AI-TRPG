import {
  createCharacter as createCharacterApi,
  getCampaign as getCampaignApi,
  listCharacters,
  loadCharacterToCampaign as loadCharacterToCampaignApi,
  selectActor as selectActorApi,
} from "../api/api.js";

const BASE_URL_KEY = "raw-console-base-url";

const state = {
  baseUrl: "",
  statusMessage: "Idle",
  campaignId: null,
  campaign: {
    party_character_ids: [],
    active_actor_id: "",
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
  partyActors: [],
  initiativeOrder: [],
  plannerActorId: null,
  plannedActions: {},
  actionInputs: {},
  failurePolicy: "stop",
  roundState: "idle",
  roundNumber: 0,
  stateSummary: null,
  mapView: null,
  turnHistory: [],
  debug: {
    requestText: "",
    responseText: "",
    traces: [],
  },
};

const subscribers = new Set();

function emit() {
  for (const subscriber of subscribers) {
    subscriber(getState());
  }
}

function normalizeBaseUrl(raw) {
  return (raw || "").trim().replace(/\/+$/, "");
}

function applyPartyActorsToState(actorIds) {
  const normalized = Array.isArray(actorIds)
    ? actorIds
        .filter((value) => typeof value === "string" && value.trim())
        .map((value) => value.trim())
    : [];
  state.partyActors = [...new Set(normalized)];
  state.campaign.party_character_ids = [...state.partyActors];
  state.initiativeOrder = [...state.partyActors];
  if (!state.plannerActorId || !state.partyActors.includes(state.plannerActorId)) {
    state.plannerActorId = state.partyActors[0] || null;
  }
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
  emit();
}

export function setPartyActors(actorIds) {
  applyPartyActorsToState(actorIds);
  emit();
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
  }
  if (typeof result.data.character_id === "string") {
    state.character.selected_character_id = result.data.character_id;
  }
  state.character.status = "idle";
  state.character.error = null;
  emit();
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
  state.statusMessage = `Active actor set to ${normalizedActorId}.`;
  emit();
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
    state.statusMessage = `Refresh campaign failed: ${parseApiError(result)}`;
    emit();
    return result;
  }

  const selected =
    result.data.selected && typeof result.data.selected === "object"
      ? result.data.selected
      : {};
  const normalizedParty = [
    ...new Set(
      Array.isArray(selected.party_character_ids)
        ? selected.party_character_ids
            .filter((value) => typeof value === "string" && value.trim())
            .map((value) => value.trim())
        : []
    ),
  ];
  const backendActiveActorId =
    typeof selected.active_actor_id === "string"
      ? selected.active_actor_id.trim()
      : "";
  applyPartyActorsToState(normalizedParty);
  state.campaignId = resolvedCampaignId;
  state.campaign.active_actor_id = backendActiveActorId;
  state.statusMessage = `Campaign refreshed from backend: active=${state.campaign.active_actor_id || "none"}, party=${state.campaign.party_character_ids.length}.`;
  emit();
  return result;
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
  if (!state.plannerActorId || !state.initiativeOrder.includes(state.plannerActorId)) {
    state.plannerActorId = state.initiativeOrder[0] || null;
  }
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

export function setPlannerActorId(actorId) {
  if (!actorId || !state.partyActors.includes(actorId)) {
    state.plannerActorId = state.partyActors[0] || null;
    emit();
    return;
  }
  state.plannerActorId = actorId;
  emit();
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
  if (
    !state.plannerActorId &&
    mapView &&
    typeof mapView === "object" &&
    typeof mapView.active_actor_id === "string" &&
    mapView.active_actor_id.trim()
  ) {
    state.plannerActorId = mapView.active_actor_id.trim();
  }
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
