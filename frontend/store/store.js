import {
  createCampaign as createCampaignApi,
  createCharacter as createCharacterApi,
  generateWorld as generateWorldApi,
  getCampaign as getCampaignApi,
  getCampaignWorld as getCampaignWorldApi,
  getMapView as getMapViewApi,
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
  mapView: null,
  inventoryStacksByActor: {},
  inventoryByActor: {},
  inventoryStackIdsByActor: {},
  inventoryAuthoritySourceByActor: {},
  selectedStackIdByActor: {},
  selectedSceneTargetIdByActor: {},
  selectionAuditByActor: {},
  submitSelectionAuditByActor: {},
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

function normalizeInventoryStackView(rawStack, fallbackActorId = "") {
  if (!rawStack || typeof rawStack !== "object" || Array.isArray(rawStack)) {
    return null;
  }
  const stackId = normalizeStackId(rawStack.stack_id);
  const itemId = normalizeItemId(rawStack.item_id);
  const quantity = Number(rawStack.quantity);
  const ownerActorId =
    normalizeActorId(rawStack.owner_actor_id) || normalizeActorId(fallbackActorId);
  const location =
    rawStack.location && typeof rawStack.location === "object" && !Array.isArray(rawStack.location)
      ? rawStack.location
      : null;
  const locationType =
    typeof location?.type === "string" && location.type.trim() ? location.type.trim() : "actor";
  const locationId =
    normalizeStringId(location?.id) || ownerActorId || normalizeStringId(rawStack.parent_id);
  const label = typeof rawStack.label === "string" ? rawStack.label.trim() : "";
  if (!stackId || !itemId || !Number.isInteger(quantity) || quantity <= 0 || !ownerActorId) {
    return null;
  }
  if (!locationId) {
    return null;
  }
  return {
    stack_id: stackId,
    item_id: itemId,
    quantity,
    owner_actor_id: ownerActorId,
    location: {
      type: locationType,
      id: locationId,
    },
    label,
  };
}

function normalizeInventoryStacks(rawInventoryStacks, fallbackActorId = "") {
  if (!Array.isArray(rawInventoryStacks)) {
    return [];
  }
  const normalized = [];
  const seen = new Set();
  for (const rawStack of rawInventoryStacks) {
    const stack = normalizeInventoryStackView(rawStack, fallbackActorId);
    if (!stack || seen.has(stack.stack_id)) {
      continue;
    }
    normalized.push(stack);
    seen.add(stack.stack_id);
  }
  normalized.sort((left, right) => left.stack_id.localeCompare(right.stack_id));
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

function normalizeInventoryStacksByActor(rawInventoryStacksByActor) {
  const normalized = {};
  if (
    !rawInventoryStacksByActor ||
    typeof rawInventoryStacksByActor !== "object" ||
    Array.isArray(rawInventoryStacksByActor)
  ) {
    return normalized;
  }
  for (const [rawActorId, rawInventoryStacks] of Object.entries(rawInventoryStacksByActor)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      continue;
    }
    normalized[actorId] = normalizeInventoryStacks(rawInventoryStacks, actorId);
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

function deriveInventoryByActorFromStacks(stacksByActor) {
  const normalizedStacksByActor =
    stacksByActor && typeof stacksByActor === "object" && !Array.isArray(stacksByActor)
      ? stacksByActor
      : {};
  const inventoryByActor = {};
  for (const [rawActorId, rawStacks] of Object.entries(normalizedStacksByActor)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      continue;
    }
    const inventory = {};
    const stacks = Array.isArray(rawStacks) ? rawStacks : [];
    for (const stack of stacks) {
      const itemId = normalizeItemId(stack?.item_id);
      const quantity = Number(stack?.quantity);
      if (!itemId || !Number.isInteger(quantity) || quantity <= 0) {
        continue;
      }
      inventory[itemId] = (inventory[itemId] || 0) + quantity;
    }
    inventoryByActor[actorId] = inventory;
  }
  return inventoryByActor;
}

function deriveInventoryStackIdsByActorFromStacks(stacksByActor) {
  const normalizedStacksByActor =
    stacksByActor && typeof stacksByActor === "object" && !Array.isArray(stacksByActor)
      ? stacksByActor
      : {};
  const stackIdsByActor = {};
  for (const [rawActorId, rawStacks] of Object.entries(normalizedStacksByActor)) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      continue;
    }
    const inventoryStackIds = {};
    const stacks = Array.isArray(rawStacks) ? rawStacks : [];
    for (const stack of stacks) {
      const itemId = normalizeItemId(stack?.item_id);
      const stackId = normalizeStackId(stack?.stack_id);
      if (!itemId || !stackId) {
        continue;
      }
      if (!Array.isArray(inventoryStackIds[itemId])) {
        inventoryStackIds[itemId] = [];
      }
      inventoryStackIds[itemId].push(stackId);
    }
    for (const stackIds of Object.values(inventoryStackIds)) {
      stackIds.sort((left, right) => left.localeCompare(right));
    }
    stackIdsByActor[actorId] = inventoryStackIds;
  }
  return stackIdsByActor;
}

function buildCompatibilityStackId(actorId, itemId) {
  const actorSlug = normalizeActorId(actorId).replace(/[^A-Za-z0-9_-]+/g, "_");
  const itemSlug = normalizeItemId(itemId).replace(/[^A-Za-z0-9_-]+/g, "_");
  return normalizeStackId(`compat_${actorSlug || "actor"}_${itemSlug || "item"}`);
}

function buildFallbackInventoryStacksForActor(actorId, rawInventory, rawInventoryStackIds) {
  const inventory = normalizeInventory(rawInventory);
  const inventoryStackIds = normalizeInventoryStackIds(rawInventoryStackIds);
  const itemIds = [...new Set([...Object.keys(inventory), ...Object.keys(inventoryStackIds)])].sort();
  const stacks = [];
  for (const itemId of itemIds) {
    const stackIds = Array.isArray(inventoryStackIds[itemId]) ? inventoryStackIds[itemId] : [];
    const totalQuantity = Number.isInteger(inventory[itemId]) && inventory[itemId] > 0 ? inventory[itemId] : 0;
    if (stackIds.length > 0) {
      const normalizedTotal = Math.max(totalQuantity, stackIds.length);
      const extraForFirst = normalizedTotal - stackIds.length;
      stackIds.forEach((stackId, index) => {
        stacks.push({
          stack_id: stackId,
          item_id: itemId,
          quantity: 1 + (index === 0 ? extraForFirst : 0),
          owner_actor_id: actorId,
          location: {
            type: "actor",
            id: actorId,
          },
          label: "",
        });
      });
      continue;
    }
    if (totalQuantity <= 0) {
      continue;
    }
    stacks.push({
      stack_id: buildCompatibilityStackId(actorId, itemId),
      item_id: itemId,
      quantity: totalQuantity,
      owner_actor_id: actorId,
      location: {
        type: "actor",
        id: actorId,
      },
      label: "",
    });
  }
  stacks.sort((left, right) => left.stack_id.localeCompare(right.stack_id));
  return stacks;
}

function buildFallbackInventoryStacksByActor(
  rawInventories,
  rawInventoryStackIdsByActor = null,
  actorIds = []
) {
  const inventoriesByActor = normalizeInventoriesByActor(rawInventories);
  const inventoryStackIdsByActor = normalizeInventoryStackIdsByActor(rawInventoryStackIdsByActor);
  const normalizedActorIds = [
    ...new Set(
      [
        ...actorIds.map(normalizeActorId),
        ...Object.keys(inventoriesByActor),
        ...Object.keys(inventoryStackIdsByActor),
      ].filter(Boolean)
    ),
  ].sort();
  const stacksByActor = {};
  for (const actorId of normalizedActorIds) {
    stacksByActor[actorId] = buildFallbackInventoryStacksForActor(
      actorId,
      inventoriesByActor[actorId],
      inventoryStackIdsByActor[actorId]
    );
  }
  return stacksByActor;
}

function normalizeStringList(values) {
  if (!Array.isArray(values)) {
    return [];
  }
  return [...new Set(values.map(normalizeStringId).filter(Boolean))];
}

function normalizeSceneEntityView(rawEntity) {
  if (!rawEntity || typeof rawEntity !== "object" || Array.isArray(rawEntity)) {
    return null;
  }
  const id = normalizeStringId(rawEntity.id);
  const kind = normalizeStringId(rawEntity.kind);
  const label = normalizeStringId(rawEntity.label);
  if (!id || !kind) {
    return null;
  }
  return {
    id,
    kind,
    label: label || id,
    tags: normalizeStringList(rawEntity.tags),
    verbs: normalizeStringList(rawEntity.verbs),
    state:
      rawEntity.state && typeof rawEntity.state === "object" && !Array.isArray(rawEntity.state)
        ? { ...rawEntity.state }
        : {},
  };
}

function normalizeMapAreaView(rawArea) {
  if (!rawArea || typeof rawArea !== "object" || Array.isArray(rawArea)) {
    return null;
  }
  const id = normalizeStringId(rawArea.id);
  const name = normalizeStringId(rawArea.name);
  if (!id) {
    return null;
  }
  return {
    id,
    name: name || id,
  };
}

function normalizeMapViewPayload(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return null;
  }
  const campaignId = normalizeStringId(payload.campaign_id);
  const activeActorId = normalizeActorId(payload.active_actor_id);
  const currentArea = normalizeMapAreaView(payload.current_area);
  if (!campaignId || !activeActorId || !currentArea) {
    return null;
  }
  return {
    campaign_id: campaignId,
    active_actor_id: activeActorId,
    current_area: currentArea,
    current_area_actor_ids: normalizeStringList(payload.current_area_actor_ids),
    reachable_areas: Array.isArray(payload.reachable_areas)
      ? payload.reachable_areas.map(normalizeMapAreaView).filter(Boolean)
      : [],
    entities_in_area: Array.isArray(payload.entities_in_area)
      ? payload.entities_in_area.map(normalizeSceneEntityView).filter(Boolean)
      : [],
  };
}

function isTakeableSceneEntity(entity) {
  return Boolean(
    entity &&
      typeof entity === "object" &&
      normalizeStringList(entity.verbs).includes("take")
  );
}

function getSceneEntitiesForActor(actorId) {
  const normalizedActorId = normalizeActorId(actorId);
  const mapView =
    state.mapView && typeof state.mapView === "object" && !Array.isArray(state.mapView)
      ? state.mapView
      : null;
  if (!normalizedActorId || !mapView || mapView.active_actor_id !== normalizedActorId) {
    return [];
  }
  return Array.isArray(mapView.entities_in_area) ? mapView.entities_in_area : [];
}

function reconcileSelectedSceneTargetWithMapView() {
  const mapView =
    state.mapView && typeof state.mapView === "object" && !Array.isArray(state.mapView)
      ? state.mapView
      : null;
  if (!mapView) {
    return;
  }
  const actorId = normalizeActorId(mapView.active_actor_id);
  if (!actorId) {
    return;
  }
  const selectedTargetId = normalizeStringId(state.selectedSceneTargetIdByActor[actorId]);
  if (!selectedTargetId) {
    return;
  }
  const selectedTarget = getSceneEntitiesForActor(actorId).find(
    (entity) => entity.id === selectedTargetId
  );
  if (selectedTarget && isTakeableSceneEntity(selectedTarget)) {
    return;
  }
  state.selectedSceneTargetIdByActor = {
    ...state.selectedSceneTargetIdByActor,
    [actorId]: null,
  };
}

function getActorInventoryStacks(actorId) {
  if (!hasOwn(state.inventoryStacksByActor, actorId)) {
    return null;
  }
  const actorStacks = state.inventoryStacksByActor[actorId];
  return Array.isArray(actorStacks) ? actorStacks : [];
}

function findInventoryStack(actorId, stackId) {
  const normalizedActorId = normalizeActorId(actorId);
  const normalizedStackId = normalizeStackId(stackId);
  if (!normalizedActorId || !normalizedStackId) {
    return null;
  }
  const actorStacks = getActorInventoryStacks(normalizedActorId);
  if (!actorStacks) {
    return null;
  }
  for (const stack of actorStacks) {
    if (normalizeStackId(stack?.stack_id) === normalizedStackId) {
      return stack;
    }
  }
  return null;
}

function resolveStackCandidatesForItem(actorId, itemId) {
  const normalizedActorId = normalizeActorId(actorId);
  const normalizedItemId = normalizeItemId(itemId);
  if (!normalizedActorId || !normalizedItemId) {
    return [];
  }
  const actorStacks = getActorInventoryStacks(normalizedActorId);
  if (!actorStacks) {
    return [];
  }
  return actorStacks
    .filter((stack) => normalizeItemId(stack?.item_id) === normalizedItemId)
    .map((stack) => normalizeStackId(stack?.stack_id))
    .filter(Boolean)
    .sort((left, right) => left.localeCompare(right));
}

function resolveSelectedItemIdFromStack(actorId, stackId) {
  return normalizeItemId(findInventoryStack(actorId, stackId)?.item_id);
}

function resolveSelectedItemIdFromAudit(actorId, rawAudit = null) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return "";
  }
  const audit = normalizeSelectionAudit(
    rawAudit ?? state.selectionAuditByActor[normalizedActorId],
    normalizedActorId
  );
  if (!audit) {
    return "";
  }
  return normalizeItemId(audit.requested_item_id || audit.selected_item_id);
}

export function getSelectedItemIdForActor(actorId) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return null;
  }
  const selectedItemId = resolveSelectedItemIdFromStack(
    normalizedActorId,
    state.selectedStackIdByActor[normalizedActorId]
  );
  if (selectedItemId) {
    return selectedItemId;
  }
  const fallbackItemId = resolveSelectedItemIdFromAudit(normalizedActorId);
  return fallbackItemId || null;
}

function normalizeSelectionAudit(rawAudit, fallbackActorId = "") {
  if (!rawAudit || typeof rawAudit !== "object" || Array.isArray(rawAudit)) {
    return null;
  }
  const mode =
    typeof rawAudit.mode === "string" && rawAudit.mode.trim() ? rawAudit.mode.trim() : "";
  const actorId =
    normalizeActorId(rawAudit.actor_id) || normalizeActorId(fallbackActorId);
  if (!mode || !actorId) {
    return null;
  }
  const audit = {
    mode,
    actor_id: actorId,
  };
  const selectedStackId = normalizeStackId(rawAudit.selected_stack_id);
  const selectedItemId = normalizeItemId(rawAudit.selected_item_id);
  const requestedItemId = normalizeItemId(rawAudit.requested_item_id);
  const reason =
    typeof rawAudit.reason === "string" && rawAudit.reason.trim() ? rawAudit.reason.trim() : "";
  const candidateStackIds = Array.isArray(rawAudit.candidate_stack_ids)
    ? [...new Set(rawAudit.candidate_stack_ids.map(normalizeStackId).filter(Boolean))]
    : [];
  if (selectedStackId) {
    audit.selected_stack_id = selectedStackId;
  }
  if (selectedItemId) {
    audit.selected_item_id = selectedItemId;
  }
  if (requestedItemId) {
    audit.requested_item_id = requestedItemId;
  }
  if (reason) {
    audit.reason = reason;
  }
  if (candidateStackIds.length > 0) {
    audit.candidate_stack_ids = candidateStackIds;
  }
  return audit;
}

function setSelectionAuditForActor(actorId, audit) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return;
  }
  state.selectionAuditByActor = {
    ...state.selectionAuditByActor,
    [normalizedActorId]: normalizeSelectionAudit(audit, normalizedActorId),
  };
}

function setSubmitSelectionAuditForActor(actorId, audit) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return;
  }
  state.submitSelectionAuditByActor = {
    ...state.submitSelectionAuditByActor,
    [normalizedActorId]: normalizeSelectionAudit(audit, normalizedActorId),
  };
}

function logSelectionAudit(audit) {
  if (!audit || typeof console !== "object" || console === null) {
    return;
  }
  const actorId = normalizeActorId(audit.actor_id) || "unknown_actor";
  if (audit.mode === "item_adapter" && typeof console.info === "function") {
    console.info(
      `[selection:item_adapter] actor=${actorId} item=${audit.requested_item_id || audit.selected_item_id || "unknown_item"} stack=${audit.selected_stack_id || "none"}`
    );
    return;
  }
  if (audit.mode === "item_fallback" && typeof console.warn === "function") {
    console.warn(
      `[selection:item_fallback] actor=${actorId} item=${audit.selected_item_id || audit.requested_item_id || "unknown_item"} reason=${audit.reason || "stack_unresolved"}`
    );
  }
}

function applySelectionForActor(actorId, stackId, audit = null) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return;
  }
  state.selectedStackIdByActor = {
    ...state.selectedStackIdByActor,
    [normalizedActorId]: normalizeStackId(stackId) || null,
  };
  setSelectionAuditForActor(normalizedActorId, audit);
}

function reconcileSelectedItemsWithInventory() {
  let changed = false;
  const nextStackSelections = {
    ...state.selectedStackIdByActor,
  };
  const nextSelectionAudit = {
    ...state.selectionAuditByActor,
  };
  const actorIds = new Set([
    ...Object.keys(nextStackSelections),
    ...Object.keys(nextSelectionAudit),
  ]);
  for (const rawActorId of actorIds) {
    const actorId = normalizeActorId(rawActorId);
    if (!actorId) {
      delete nextStackSelections[rawActorId];
      delete nextSelectionAudit[rawActorId];
      changed = true;
      continue;
    }
    const hasKnownStacks = hasOwn(state.inventoryStacksByActor, actorId);
    const currentAudit = normalizeSelectionAudit(nextSelectionAudit[actorId], actorId);
    const currentStack = findInventoryStack(actorId, nextStackSelections[actorId]);
    let nextItemId = null;
    let nextStackId = null;
    let nextAudit = null;

    if (currentStack) {
      nextStackId = normalizeStackId(currentStack.stack_id) || null;
      nextItemId = normalizeItemId(currentStack.item_id) || null;
      nextAudit =
        currentAudit && currentAudit.mode !== "item_fallback"
          ? {
              ...currentAudit,
              actor_id: actorId,
              selected_stack_id: nextStackId,
              selected_item_id: nextItemId,
            }
          : {
              mode: "stack_primary",
              actor_id: actorId,
              selected_stack_id: nextStackId,
              selected_item_id: nextItemId,
              reason: "reconciled_from_stack",
            };
    } else if (
      currentAudit &&
      currentAudit.mode === "item_fallback" &&
      !hasKnownStacks &&
      resolveSelectedItemIdFromAudit(actorId, currentAudit)
    ) {
      nextItemId = resolveSelectedItemIdFromAudit(actorId, currentAudit) || null;
      nextAudit = {
        ...currentAudit,
        actor_id: actorId,
        selected_item_id: nextItemId,
      };
    }

    if ((nextStackSelections[actorId] || null) !== nextStackId) {
      nextStackSelections[actorId] = nextStackId;
      changed = true;
    }
    const normalizedCurrentAudit = normalizeSelectionAudit(nextSelectionAudit[actorId], actorId);
    const normalizedNextAudit = normalizeSelectionAudit(nextAudit, actorId);
    if (JSON.stringify(normalizedCurrentAudit) !== JSON.stringify(normalizedNextAudit)) {
      nextSelectionAudit[actorId] = normalizedNextAudit;
      changed = true;
    }
  }
  if (changed) {
    state.selectedStackIdByActor = nextStackSelections;
    state.selectionAuditByActor = nextSelectionAudit;
  }
  return changed;
}

function applyDerivedInventoryViews(stacksByActor, authoritySourceByActor = null) {
  state.inventoryStacksByActor = normalizeInventoryStacksByActor(stacksByActor);
  state.inventoryByActor = deriveInventoryByActorFromStacks(state.inventoryStacksByActor);
  state.inventoryStackIdsByActor = deriveInventoryStackIdsByActorFromStacks(state.inventoryStacksByActor);
  state.inventoryAuthoritySourceByActor =
    authoritySourceByActor && typeof authoritySourceByActor === "object" && !Array.isArray(authoritySourceByActor)
      ? { ...authoritySourceByActor }
      : {};
}

function replaceInventoryByStacks(rawInventoryStacksByActor, authoritySourceByActor = null) {
  applyDerivedInventoryViews(rawInventoryStacksByActor, authoritySourceByActor);
  reconcileSelectedItemsWithInventory();
}

function replaceInventoryByCompatibilityFallback(
  rawInventories,
  rawInventoryStackIdsByActor = null,
  actorIds = []
) {
  const stacksByActor = buildFallbackInventoryStacksByActor(
    rawInventories,
    rawInventoryStackIdsByActor,
    actorIds
  );
  const authoritySourceByActor = Object.fromEntries(
    Object.keys(stacksByActor).map((actorId) => [actorId, "compatibility"])
  );
  replaceInventoryByStacks(stacksByActor, authoritySourceByActor);
}

function patchInventoryStacksForActor(actorId, rawInventoryStacks, source = "stack") {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return;
  }
  const normalizedStacks = normalizeInventoryStacks(rawInventoryStacks, normalizedActorId);
  applyDerivedInventoryViews(
    {
      ...state.inventoryStacksByActor,
      [normalizedActorId]: normalizedStacks,
    },
    {
      ...state.inventoryAuthoritySourceByActor,
      [normalizedActorId]: source,
    }
  );
  reconcileSelectedItemsWithInventory();
}

function patchInventoryForActorCompatibilityFallback(actorId, rawInventory, rawInventoryStackIds = null) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return;
  }
  patchInventoryStacksForActor(
    normalizedActorId,
    buildFallbackInventoryStacksForActor(normalizedActorId, rawInventory, rawInventoryStackIds),
    "compatibility"
  );
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
    state.mapView = null;
  }
  emit();
}

export function setPartyActors(actorIds) {
  applyPartyActorsToState(actorIds);
  emit();
}

export function setSelectedStackForActor(actorId, stackId, options = {}) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return false;
  }
  const normalizedStackId = normalizeStackId(stackId);
  if (!normalizedStackId) {
    applySelectionForActor(normalizedActorId, null, null);
    emit();
    return true;
  }
  const selectedStack = findInventoryStack(normalizedActorId, normalizedStackId);
  if (!selectedStack) {
    return false;
  }
  const currentStackId = normalizeStackId(state.selectedStackIdByActor[normalizedActorId]);
  const toggleOff = currentStackId === normalizedStackId;
  const nextAudit = toggleOff
    ? null
    : {
        mode:
          typeof options.mode === "string" && options.mode.trim()
            ? options.mode.trim()
            : "stack_primary",
        actor_id: normalizedActorId,
        selected_stack_id: normalizedStackId,
        selected_item_id: normalizeItemId(selectedStack.item_id),
        requested_item_id: normalizeItemId(options.requestedItemId),
        reason:
          typeof options.reason === "string" && options.reason.trim()
            ? options.reason.trim()
            : "",
        candidate_stack_ids: Array.isArray(options.candidateStackIds)
          ? options.candidateStackIds
          : [],
      };
  applySelectionForActor(
    normalizedActorId,
    toggleOff ? null : normalizedStackId,
    nextAudit
  );
  if (!toggleOff) {
    logSelectionAudit(nextAudit);
  }
  emit();
  return true;
}

export function setSelectedItemForActor(actorId, itemId) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return false;
  }
  const normalizedItemId = normalizeItemId(itemId);
  if (!normalizedItemId) {
    applySelectionForActor(normalizedActorId, null, null);
    emit();
    return true;
  }
  const candidateStackIds = resolveStackCandidatesForItem(normalizedActorId, normalizedItemId);
  if (candidateStackIds.length > 0) {
    return setSelectedStackForActor(normalizedActorId, candidateStackIds[0], {
      mode: "item_adapter",
      requestedItemId: normalizedItemId,
      candidateStackIds,
      reason: candidateStackIds.length > 1 ? "deterministic_first_stack" : "single_stack_match",
    });
  }
  const hasKnownStacks = hasOwn(state.inventoryStacksByActor, normalizedActorId);
  const inventory = state.inventoryByActor[normalizedActorId];
  if (!hasKnownStacks && inventory && hasOwn(inventory, normalizedItemId)) {
    const nextAudit = {
      mode: "item_fallback",
      actor_id: normalizedActorId,
      selected_item_id: normalizedItemId,
      requested_item_id: normalizedItemId,
      reason: "stack_unresolved",
    };
    applySelectionForActor(normalizedActorId, null, nextAudit);
    logSelectionAudit(nextAudit);
    emit();
    return true;
  }
  return false;
}

export function setSelectedSceneTargetForActor(actorId, targetId) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return false;
  }
  const normalizedTargetId = normalizeStringId(targetId);
  if (!normalizedTargetId) {
    state.selectedSceneTargetIdByActor = {
      ...state.selectedSceneTargetIdByActor,
      [normalizedActorId]: null,
    };
    emit();
    return true;
  }
  const sceneTarget = getSceneEntitiesForActor(normalizedActorId).find(
    (entity) => entity.id === normalizedTargetId
  );
  if (!sceneTarget || !isTakeableSceneEntity(sceneTarget)) {
    return false;
  }
  const currentTargetId = normalizeStringId(state.selectedSceneTargetIdByActor[normalizedActorId]);
  state.selectedSceneTargetIdByActor = {
    ...state.selectedSceneTargetIdByActor,
    [normalizedActorId]: currentTargetId === normalizedTargetId ? null : normalizedTargetId,
  };
  emit();
  return true;
}

export function getSelectedSceneTargetForActor(actorId) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return null;
  }
  const selectedTargetId = normalizeStringId(state.selectedSceneTargetIdByActor[normalizedActorId]);
  if (!selectedTargetId) {
    return null;
  }
  return (
    getSceneEntitiesForActor(normalizedActorId).find((entity) => entity.id === selectedTargetId) ||
    null
  );
}

export function buildTurnContextHintsForActor(actorId) {
  const normalizedActorId = normalizeActorId(actorId);
  if (!normalizedActorId) {
    return null;
  }
  const selectedSceneTarget = getSelectedSceneTargetForActor(normalizedActorId);
  const targetHint = selectedSceneTarget ? { selected_target_id: selectedSceneTarget.id } : {};
  const selectedStack = findInventoryStack(
    normalizedActorId,
    state.selectedStackIdByActor[normalizedActorId]
  );
  if (selectedStack) {
    const audit = {
      mode: "stack_primary",
      actor_id: normalizedActorId,
      selected_stack_id: normalizeStackId(selectedStack.stack_id),
      selected_item_id: normalizeItemId(selectedStack.item_id),
    };
    setSubmitSelectionAuditForActor(normalizedActorId, audit);
    return {
      selected_stack_id: audit.selected_stack_id,
      ...targetHint,
    };
  }
  const currentAudit = normalizeSelectionAudit(
    state.selectionAuditByActor[normalizedActorId],
    normalizedActorId
  );
  const selectedItemId = resolveSelectedItemIdFromAudit(normalizedActorId, currentAudit);
  if (currentAudit?.mode === "item_fallback" && selectedItemId) {
    const audit = {
      mode: "item_fallback",
      actor_id: normalizedActorId,
      selected_item_id: selectedItemId,
      requested_item_id: currentAudit.requested_item_id || selectedItemId,
      reason: currentAudit.reason || "stack_unresolved",
    };
    setSubmitSelectionAuditForActor(normalizedActorId, audit);
    logSelectionAudit(audit);
    return {
      selected_item_id: selectedItemId,
      ...targetHint,
    };
  }
  setSubmitSelectionAuditForActor(normalizedActorId, {
    mode: "none",
    actor_id: normalizedActorId,
    reason: "no_selection",
  });
  return Object.keys(targetHint).length ? targetHint : null;
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
  const inventoryStacksByActor = normalizeInventoryStacksByActor(payload.inventory_stacks);
  const hasInventoryStacksField =
    hasOwn(payload, "inventory_stacks") &&
    payload.inventory_stacks &&
    typeof payload.inventory_stacks === "object" &&
    !Array.isArray(payload.inventory_stacks);
  const hasInventoryStackIdsField =
    hasOwn(payload, "inventory_stack_ids") &&
    payload.inventory_stack_ids &&
    typeof payload.inventory_stack_ids === "object" &&
    !Array.isArray(payload.inventory_stack_ids);
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
    inventoryStacksByActor,
    hasInventoryStacksField,
    hasInventoryStackIdsField,
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
  if (normalizedPayload.hasInventoryStacksField) {
    replaceInventoryByStacks(
      normalizedPayload.inventoryStacksByActor,
      Object.fromEntries(
        Object.keys(normalizedPayload.inventoryStacksByActor).map((actorId) => [actorId, "stack"])
      )
    );
  } else if (
    normalizedPayload.inventoriesByActor ||
    normalizedPayload.hasInventoryStackIdsField
  ) {
    replaceInventoryByCompatibilityFallback(
      normalizedPayload.inventoriesByActor,
      normalizedPayload.inventoryStackIdsByActor,
      Object.keys(normalizedPayload.actors)
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

export async function refreshMapView(
  campaignId = state.campaignId,
  actorId = state.campaign.active_actor_id,
  baseUrl = state.baseUrl,
  options = {}
) {
  const resolvedCampaignId =
    typeof campaignId === "string" && campaignId.trim() ? campaignId.trim() : "";
  const resolvedActorId =
    typeof actorId === "string" && actorId.trim() ? actorId.trim() : "";
  if (!resolvedCampaignId || !resolvedActorId) {
    state.mapView = null;
    if (options.emit !== false) {
      emit();
    }
    return {
      ok: false,
      status: 400,
      data: null,
      text: "campaign_id and actor_id are required",
    };
  }

  const result = await getMapViewApi(baseUrl, resolvedCampaignId, resolvedActorId);
  if (!result.ok || !result.data) {
    state.mapView = null;
    if (options.emit !== false) {
      emit();
    }
    return result;
  }

  const normalizedPayload = normalizeMapViewPayload(result.data);
  if (!normalizedPayload) {
    state.mapView = null;
    if (options.emit !== false) {
      emit();
    }
    return {
      ok: false,
      status: result.status || 500,
      data: { detail: "map/view returned invalid payload" },
      text: result.text,
    };
  }

  state.mapView = normalizedPayload;
  reconcileSelectedSceneTargetWithMapView();
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
    if (
      hasOwn(payload.state_summary, "inventory_stacks") &&
      payload.state_summary.inventory_stacks &&
      typeof payload.state_summary.inventory_stacks === "object" &&
      !Array.isArray(payload.state_summary.inventory_stacks)
    ) {
      replaceInventoryByStacks(
        payload.state_summary.inventory_stacks,
        Object.fromEntries(
          Object.keys(normalizeInventoryStacksByActor(payload.state_summary.inventory_stacks)).map(
            (actorId) => [actorId, "stack"]
          )
        )
      );
    } else if (
      effectiveActorId &&
      hasOwn(payload.state_summary, "active_actor_inventory_stacks") &&
      Array.isArray(payload.state_summary.active_actor_inventory_stacks)
    ) {
      patchInventoryStacksForActor(
        effectiveActorId,
        payload.state_summary.active_actor_inventory_stacks,
        "stack"
      );
    } else if (payload.state_summary.inventories && typeof payload.state_summary.inventories === "object") {
      replaceInventoryByCompatibilityFallback(
        payload.state_summary.inventories,
        payload.state_summary.inventory_stack_ids
      );
    } else if (effectiveActorId && payload.state_summary.active_actor_inventory) {
      patchInventoryForActorCompatibilityFallback(
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
