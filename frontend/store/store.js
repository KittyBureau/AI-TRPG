import {
  createCampaign as createCampaignApi,
  createCharacter as createCharacterApi,
  generateWorld as generateWorldApi,
  getCampaign as getCampaignApi,
  getCampaignWorld as getCampaignWorldApi,
  getRuntimeStatus as getRuntimeStatusApi,
  listCampaigns as listCampaignsApi,
  listCharacters,
  listWorlds as listWorldsApi,
  loadCharacterToCampaign as loadCharacterToCampaignApi,
  selectActor as selectActorApi,
} from "../api/api.js";

const BASE_URL_KEY = "raw-console-base-url";
const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";
const SCENARIO_GENERATOR_ID = "playable_scenario_v0";
const DEFAULT_SCENARIO_TEMPLATE = "key_gate_scenario";
const DEFAULT_SCENARIO_THEME = "watchtower";
const DEFAULT_SCENARIO_AREA_COUNT = "6";
const DEFAULT_SCENARIO_LAYOUT_TYPE = "branch";
const DEFAULT_SCENARIO_DIFFICULTY = "easy";

const state = {
  baseUrl: "",
  statusMessage: "Idle",
  campaignId: null,
  campaign: {
    party_character_ids: [],
    active_actor_id: "",
    status: null,
    actors: {},
    map: {
      areas: {},
    },
    world: null,
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
  worlds: {
    list: [],
    status: "idle",
    error: null,
    generate_form: {
      world_id: "",
      name: "",
      mode: "stub",
      scenario_template: DEFAULT_SCENARIO_TEMPLATE,
      scenario_theme: DEFAULT_SCENARIO_THEME,
      scenario_area_count: DEFAULT_SCENARIO_AREA_COUNT,
      scenario_layout_type: DEFAULT_SCENARIO_LAYOUT_TYPE,
      scenario_difficulty: DEFAULT_SCENARIO_DIFFICULTY,
    },
    last_generated_world_id: null,
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
  inventoryStackIdsByActor: {},
  selectedStackIdByActor: {},
  selectedItemIdByActor: {},
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

function normalizeStringId(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizeActorId(value) {
  return normalizeStringId(value);
}

function normalizeItemId(value) {
  return normalizeStringId(value);
}

function normalizeStackId(value) {
  return normalizeStringId(value);
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

function normalizeInventoryStackIds(rawInventoryStackIds) {
  const normalized = {};
  if (
    !rawInventoryStackIds ||
    typeof rawInventoryStackIds !== "object" ||
    Array.isArray(rawInventoryStackIds)
  ) {
    return normalized;
  }
  for (const [rawItemId, rawStackIds] of Object.entries(rawInventoryStackIds)) {
    const itemId = normalizeItemId(rawItemId);
    if (!itemId) {
      continue;
    }
    const candidateStackIds = Array.isArray(rawStackIds) ? rawStackIds : [rawStackIds];
    const stackIds = [];
    const seen = new Set();
    for (const rawStackId of candidateStackIds) {
      const stackId = normalizeStackId(rawStackId);
      if (!stackId || seen.has(stackId)) {
        continue;
      }
      stackIds.push(stackId);
      seen.add(stackId);
    }
    if (stackIds.length > 0) {
      normalized[itemId] = stackIds;
    }
  }
  return normalized;
}

function normalizeInventoryStackIdsByActor(rawInventoryStackIdsByActor) {
  const normalized = {};
  if (
    !rawInventoryStackIdsByActor ||
    typeof rawInventoryStackIdsByActor !== "object" ||
    Array.isArray(rawInventoryStackIdsByActor)
  ) {
    return normalized;
  }
  for (const [rawActorId, rawInventoryStackIds] of Object.entries(rawInventoryStackIdsByActor)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      continue;
    }
    normalized[actorId] = normalizeInventoryStackIds(rawInventoryStackIds);
  }
  return normalized;
}

function getKnownInventoryStackIds(actorId) {
  if (!hasOwn(state.inventoryStackIdsByActor, actorId)) {
    return null;
  }
  const inventoryStackIds = state.inventoryStackIdsByActor[actorId];
  if (!inventoryStackIds || typeof inventoryStackIds !== "object" || Array.isArray(inventoryStackIds)) {
    return {};
  }
  return inventoryStackIds;
}

function resolvePreferredStackIdForItem(actorId, itemId) {
  const inventoryStackIds = getKnownInventoryStackIds(actorId);
  if (!inventoryStackIds || !Array.isArray(inventoryStackIds[itemId])) {
    return "";
  }
  return normalizeStackId(inventoryStackIds[itemId][0]);
}

function resolveSelectedItemIdFromStack(actorId, stackId) {
  const normalizedStackId = normalizeStackId(stackId);
  if (!normalizedStackId) {
    return "";
  }
  const inventoryStackIds = getKnownInventoryStackIds(actorId);
  if (!inventoryStackIds) {
    return "";
  }
  for (const [itemId, stackIds] of Object.entries(inventoryStackIds)) {
    if (!Array.isArray(stackIds)) {
      continue;
    }
    if (stackIds.some((candidate) => normalizeStackId(candidate) === normalizedStackId)) {
      return itemId;
    }
  }
  return "";
}

function reconcileSelectedItemsWithInventory() {
  let changed = false;
  const nextItemSelections = {
    ...state.selectedItemIdByActor,
  };
  const nextStackSelections = {
    ...state.selectedStackIdByActor,
  };
  const actorIds = new Set([
    ...Object.keys(nextItemSelections),
    ...Object.keys(nextStackSelections),
  ]);
  for (const rawActorId of actorIds) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      delete nextItemSelections[rawActorId];
      delete nextStackSelections[rawActorId];
      changed = true;
      continue;
    }
    const inventory =
      hasOwn(state.inventoryByActor, actorId) &&
      state.inventoryByActor[actorId] &&
      typeof state.inventoryByActor[actorId] === "object"
        ? state.inventoryByActor[actorId]
        : {};
    const hasKnownStackIds = getKnownInventoryStackIds(actorId) !== null;
    let itemId = normalizeItemId(nextItemSelections[actorId]);
    let stackId = normalizeStackId(nextStackSelections[actorId]);

    if (stackId) {
      const resolvedItemId = resolveSelectedItemIdFromStack(actorId, stackId);
      if (resolvedItemId) {
        itemId = resolvedItemId;
      } else if (hasKnownStackIds) {
        itemId = "";
        stackId = "";
      }
    }

    if (!stackId && itemId && hasKnownStackIds) {
      stackId = resolvePreferredStackIdForItem(actorId, itemId);
    }

    if (itemId && hasOwn(state.inventoryByActor, actorId) && !hasOwn(inventory, itemId)) {
      itemId = "";
      stackId = "";
    }

    const nextItemId = itemId || null;
    const nextStackId = stackId || null;
    if ((nextItemSelections[actorId] || null) !== nextItemId) {
      nextItemSelections[actorId] = nextItemId;
      changed = true;
    }
    if ((nextStackSelections[actorId] || null) !== nextStackId) {
      nextStackSelections[actorId] = nextStackId;
      changed = true;
    }
  }
  if (changed) {
    state.selectedItemIdByActor = nextItemSelections;
    state.selectedStackIdByActor = nextStackSelections;
  }
  return changed;
}

function replaceInventoryByActor(rawInventories, rawInventoryStackIdsByActor = null) {
  state.inventoryByActor = normalizeInventoriesByActor(rawInventories);
  state.inventoryStackIdsByActor = normalizeInventoryStackIdsByActor(rawInventoryStackIdsByActor);
  reconcileSelectedItemsWithInventory();
}

function patchInventoryForActor(actorId, rawInventory, rawInventoryStackIds = null) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return;
  }
  state.inventoryByActor = {
    ...state.inventoryByActor,
    [normalizedActorId]: normalizeInventory(rawInventory),
  };
  if (rawInventoryStackIds !== null && rawInventoryStackIds !== undefined) {
    state.inventoryStackIdsByActor = {
      ...state.inventoryStackIdsByActor,
      [normalizedActorId]: normalizeInventoryStackIds(rawInventoryStackIds),
    };
  } else {
    const nextInventoryStackIdsByActor = {
      ...state.inventoryStackIdsByActor,
    };
    delete nextInventoryStackIdsByActor[normalizedActorId];
    state.inventoryStackIdsByActor = nextInventoryStackIdsByActor;
  }
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
    state.campaign.actors = {};
    state.campaign.map = { areas: {} };
    state.campaign.world = null;
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
    state.selectedStackIdByActor = {
      ...state.selectedStackIdByActor,
      [normalizedActorId]: null,
    };
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
  const nextStackId = resolvePreferredStackIdForItem(normalizedActorId, normalizedItemId);
  const currentStackId = normalizeStackId(state.selectedStackIdByActor[normalizedActorId]);
  const currentItemId = normalizeItemId(state.selectedItemIdByActor[normalizedActorId]);
  const toggleOff = nextStackId
    ? currentStackId === nextStackId
    : currentItemId === normalizedItemId;
  state.selectedStackIdByActor = {
    ...state.selectedStackIdByActor,
    [normalizedActorId]: toggleOff ? null : nextStackId || null,
  };
  state.selectedItemIdByActor = {
    ...state.selectedItemIdByActor,
    [normalizedActorId]: toggleOff ? null : normalizedItemId,
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

export function setWorldGenerateForm(nextForm) {
  const patch =
    nextForm && typeof nextForm === "object" && !Array.isArray(nextForm)
      ? nextForm
      : {};
  state.worlds.generate_form = {
    ...state.worlds.generate_form,
    ...patch,
  };
  emit();
}

function normalizeScenarioAreaCount(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  if (!Number.isInteger(parsed) || parsed < 4 || parsed > 8) {
    return 6;
  }
  return parsed;
}

function normalizeScenarioChoice(value, allowed, fallback) {
  if (typeof value !== "string") {
    return fallback;
  }
  const normalized = value.trim().toLowerCase();
  if (!normalized) {
    return fallback;
  }
  return allowed.includes(normalized) ? normalized : fallback;
}

function buildWorldGenerateRequestPayload(form) {
  const payload = {
    world_id: typeof form?.world_id === "string" ? form.world_id : "",
    name: typeof form?.name === "string" ? form.name : "",
  };
  if (form?.mode !== "scenario") {
    return payload;
  }
  payload.generator_id = SCENARIO_GENERATOR_ID;
  payload.generator_params = {
    template_id:
      typeof form?.scenario_template === "string" && form.scenario_template.trim()
        ? form.scenario_template.trim()
        : DEFAULT_SCENARIO_TEMPLATE,
    theme:
      typeof form?.scenario_theme === "string" && form.scenario_theme.trim()
        ? form.scenario_theme.trim()
        : DEFAULT_SCENARIO_THEME,
    area_count: normalizeScenarioAreaCount(form?.scenario_area_count),
    layout_type: normalizeScenarioChoice(
      form?.scenario_layout_type,
      ["linear", "branch", "branched"],
      DEFAULT_SCENARIO_LAYOUT_TYPE
    ),
    difficulty: normalizeScenarioChoice(
      form?.scenario_difficulty,
      ["easy", "standard"],
      DEFAULT_SCENARIO_DIFFICULTY
    ),
  };
  return payload;
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

function normalizeCampaignActors(rawActors) {
  const normalized = {};
  if (Array.isArray(rawActors)) {
    for (const rawActorId of rawActors) {
      const actorId = normalizeActorId(rawActorId);
      if (!actorId) {
        continue;
      }
      normalized[actorId] = {
        position: null,
        hp: null,
        character_state: "",
      };
    }
    return normalized;
  }
  if (!rawActors || typeof rawActors !== "object") {
    return normalized;
  }
  for (const [rawActorId, rawActor] of Object.entries(rawActors)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId || !rawActor || typeof rawActor !== "object" || Array.isArray(rawActor)) {
      continue;
    }
    normalized[actorId] = {
      position: normalizeStringId(rawActor.position) || null,
      hp: Number.isFinite(rawActor.hp) ? Number(rawActor.hp) : null,
      character_state:
        typeof rawActor.character_state === "string" ? rawActor.character_state.trim() : "",
    };
  }
  return normalized;
}

function normalizeCampaignInventories(rawActors) {
  if (!rawActors || typeof rawActors !== "object" || Array.isArray(rawActors)) {
    return null;
  }
  const normalized = {};
  let sawInventoryField = false;
  for (const [rawActorId, rawActor] of Object.entries(rawActors)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId || !rawActor || typeof rawActor !== "object" || Array.isArray(rawActor)) {
      continue;
    }
    if (hasOwn(rawActor, "inventory")) {
      sawInventoryField = true;
    }
    normalized[actorId] = normalizeInventory(rawActor.inventory);
  }
  return sawInventoryField ? normalized : null;
}

function normalizeCampaignMap(rawMap) {
  const normalized = {
    areas: {},
  };
  if (!rawMap || typeof rawMap !== "object" || Array.isArray(rawMap)) {
    return normalized;
  }
  const rawAreas =
    rawMap.areas && typeof rawMap.areas === "object" && !Array.isArray(rawMap.areas)
      ? rawMap.areas
      : {};
  for (const [rawAreaId, rawArea] of Object.entries(rawAreas)) {
    const areaId = normalizeStringId(rawAreaId);
    if (!areaId || !rawArea || typeof rawArea !== "object" || Array.isArray(rawArea)) {
      continue;
    }
    normalized.areas[areaId] = {
      id: normalizeStringId(rawArea.id) || areaId,
      name: typeof rawArea.name === "string" ? rawArea.name.trim() : "",
      description: typeof rawArea.description === "string" ? rawArea.description.trim() : "",
      parent_area_id: normalizeStringId(rawArea.parent_area_id) || null,
      reachable_area_ids: Array.isArray(rawArea.reachable_area_ids)
        ? [...new Set(rawArea.reachable_area_ids.map(normalizeStringId).filter(Boolean))]
        : [],
    };
  }
  return normalized;
}

function normalizeCampaignWorld(rawWorld) {
  if (!rawWorld || typeof rawWorld !== "object" || Array.isArray(rawWorld)) {
    return null;
  }
  const worldId = normalizeStringId(rawWorld.world_id);
  if (!worldId) {
    return null;
  }
  return {
    world_id: worldId,
    name: typeof rawWorld.name === "string" ? rawWorld.name.trim() : "",
    world_description:
      typeof rawWorld.world_description === "string" ? rawWorld.world_description.trim() : "",
    objective: typeof rawWorld.objective === "string" ? rawWorld.objective.trim() : "",
    start_area: normalizeStringId(rawWorld.start_area),
  };
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
  const actors = normalizeCampaignActors(payload.actors);
  const inventoriesByActor = normalizeCampaignInventories(payload.actors);
  const inventoryStackIdsByActor = normalizeInventoryStackIdsByActor(payload.inventory_stack_ids);
  const map = normalizeCampaignMap(payload.map);
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
    actors,
    inventoriesByActor,
    inventoryStackIdsByActor,
    map,
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

export async function refreshWorlds(baseUrl = state.baseUrl, options = {}) {
  state.worlds.status = "loading";
  state.worlds.error = null;
  if (options.emit !== false) {
    emit();
  }
  const result = await listWorldsApi(baseUrl);
  if (!result.ok || !Array.isArray(result.data)) {
    state.worlds.list = [];
    state.worlds.status = "error";
    state.worlds.error = parseApiError(result);
    emit();
    return result;
  }
  state.worlds.list = result.data;
  state.worlds.status = "idle";
  state.worlds.error = null;
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

export async function generateWorldResource(baseUrl = state.baseUrl, payload = null) {
  state.worlds.status = "creating";
  state.worlds.error = null;
  emit();
  const fallbackPayload = buildWorldGenerateRequestPayload(state.worlds.generate_form);
  const requestPayload = payload && typeof payload === "object" ? payload : fallbackPayload;
  const result = await generateWorldApi(baseUrl, requestPayload);
  if (!result.ok || !result.data || typeof result.data.world_id !== "string") {
    state.worlds.status = "error";
    state.worlds.error = parseApiError(result);
    emit();
    return result;
  }
  state.worlds.last_generated_world_id = result.data.world_id;
  state.worlds.generate_form = {
    ...state.worlds.generate_form,
    world_id: "",
  };
  const refreshResult = await refreshWorlds(baseUrl, { emit: false });
  state.worlds.status = refreshResult.ok ? "idle" : "error";
  state.worlds.error = refreshResult.ok ? null : parseApiError(refreshResult);
  emit();
  return result;
}

export async function createCampaignWithSelectedParty(
  options = {},
  baseUrl = state.baseUrl
) {
  const selectedCharacterIds = Array.isArray(options?.characterIds)
    ? [...new Set(
        options.characterIds
          .filter((value) => typeof value === "string" && value.trim())
          .map((value) => value.trim())
      )]
    : [];
  if (!selectedCharacterIds.length) {
    const message = "Select at least one character.";
    state.statusMessage = message;
    emit();
    return {
      ok: false,
      status: 400,
      data: { detail: message },
      text: message,
    };
  }

  const requestedActiveActorId =
    typeof options?.activeActorId === "string" && options.activeActorId.trim()
      ? options.activeActorId.trim()
      : selectedCharacterIds[0];
  const activeActorId = selectedCharacterIds.includes(requestedActiveActorId)
    ? requestedActiveActorId
    : selectedCharacterIds[0];
  const worldId =
    typeof options?.worldId === "string" && options.worldId.trim()
      ? options.worldId.trim()
      : "";

  const createPayload = {
    party_character_ids: selectedCharacterIds,
  };
  if (worldId) {
    createPayload.world_id = worldId;
  }

  const createResult = await createCampaignApi(baseUrl, createPayload);
  if (!createResult.ok || !createResult.data || typeof createResult.data.campaign_id !== "string") {
    state.statusMessage = `Create campaign failed: ${parseApiError(createResult)}`;
    emit();
    return createResult;
  }

  const campaignId = createResult.data.campaign_id.trim();
  if (!campaignId) {
    const invalidResult = {
      ok: false,
      status: createResult.status || 500,
      data: { detail: "campaign/create returned invalid payload" },
      text: createResult.text,
    };
    state.statusMessage = `Create campaign failed: ${parseApiError(invalidResult)}`;
    emit();
    return invalidResult;
  }

  state.campaignId = campaignId;
  emit();

  const campaignsResult = await loadCampaignOptionsFromBackend(baseUrl, { silent: true });
  if (!campaignsResult.ok) {
    state.statusMessage = `Created campaign ${campaignId}, but campaign list refresh failed: ${parseApiError(campaignsResult)}`;
    emit();
    return {
      ...campaignsResult,
      campaign_id: campaignId,
    };
  }

  for (const characterId of selectedCharacterIds) {
    const loadResult = await loadCharacterToCampaign(campaignId, characterId, baseUrl);
    if (!loadResult.ok) {
      state.statusMessage = `Created campaign ${campaignId}, but party load failed for ${characterId}: ${parseApiError(loadResult)}`;
      emit();
      return {
        ...loadResult,
        campaign_id: campaignId,
      };
    }
  }

  if (activeActorId) {
    const selectResult = await selectActiveActor(activeActorId, campaignId, baseUrl);
    if (!selectResult.ok) {
      state.statusMessage = `Created campaign ${campaignId}, but active actor select failed: ${parseApiError(selectResult)}`;
      emit();
      return {
        ...selectResult,
        campaign_id: campaignId,
      };
    }
  }

  const refreshResult = await refreshCampaign(campaignId, baseUrl);
  if (!refreshResult.ok) {
    state.statusMessage = `Created campaign ${campaignId}, but refresh failed: ${parseApiError(refreshResult)}`;
    emit();
    return {
      ...refreshResult,
      campaign_id: campaignId,
    };
  }

  state.character.selected_character_id = activeActorId || selectedCharacterIds[0] || null;
  state.statusMessage = `Created campaign ${campaignId} with ${selectedCharacterIds.length} selected character(s).`;
  emit();
  return {
    ok: true,
    status: createResult.status,
    data: {
      campaign_id: campaignId,
      party_character_ids: [...state.campaign.party_character_ids],
      active_actor_id: state.campaign.active_actor_id,
    },
    text: createResult.text,
  };
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
  state.campaign.actors = normalizedPayload.actors;
  state.campaign.map = normalizedPayload.map;
  if (normalizedPayload.inventoriesByActor) {
    replaceInventoryByActor(
      normalizedPayload.inventoriesByActor,
      normalizedPayload.inventoryStackIdsByActor
    );
  } else {
    reconcileSelectedItemsWithInventory();
  }
  syncCampaignOption(normalizedPayload.campaignId, {
    active_actor_id: normalizedPayload.activeActorId,
  });
  state.statusMessage = `Campaign refreshed from backend: active=${state.campaign.active_actor_id || "none"}, party=${state.campaign.party_character_ids.length}.`;
  emit();
  return result;
}

export async function refreshCampaignWorldPreview(
  campaignId = state.campaignId,
  baseUrl = state.baseUrl,
  options = {}
) {
  const resolvedCampaignId =
    typeof campaignId === "string" && campaignId.trim() ? campaignId.trim() : "";
  if (!resolvedCampaignId) {
    state.campaign.world = null;
    if (options.emit !== false) {
      emit();
    }
    return {
      ok: false,
      status: 400,
      data: null,
      text: "campaign_id is required",
    };
  }

  const result = await getCampaignWorldApi(baseUrl, resolvedCampaignId);
  if (!result.ok || !result.data) {
    state.campaign.world = null;
    if (options.emit !== false) {
      emit();
    }
    return result;
  }

  state.campaign.world = normalizeCampaignWorld(result.data);
  if (options.emit !== false) {
    emit();
  }
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
      replaceInventoryByActor(
        payload.state_summary.inventories,
        payload.state_summary.inventory_stack_ids
      );
    } else if (effectiveActorId && payload.state_summary.active_actor_inventory) {
      patchInventoryForActor(
        effectiveActorId,
        payload.state_summary.active_actor_inventory,
        payload.state_summary.active_actor_inventory_stack_ids
      );
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
