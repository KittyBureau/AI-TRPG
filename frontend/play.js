import {
  checkBackendReady,
  createCampaignWithSelectedParty,
  createCharacter,
  generateWorldResource,
  getState,
  initializeStore,
  loadCharacterLibrary,
  loadCharacterToCampaign,
  loadCampaignOptionsFromBackend,
  buildTurnContextHintsForActor,
  getSelectedItemIdForActor,
  getSelectedSceneTargetForActor,
  refreshCampaignWorldPreview,
  refreshMapView,
  refreshWorlds,
  recoverFrontendSession,
  refreshCampaign,
  selectActiveActor,
  setBaseUrl,
  setCampaignId,
  setCampaignOptions,
  setCharacterCreateForm,
  setSelectedSceneTargetForActor,
  setWorldGenerateForm,
  setSelectedItemForActor,
  setDebugResponseText,
  recordTurnResult,
  setPartyActors,
  setStateSummary,
  setStatusMessage,
  subscribe,
} from "./store/store.js";
import { initPanel as initCampaignPanel } from "./panels/campaign_panel.js";
import { initPanel as initCharacterLibraryPanel } from "./panels/character_library_panel.js";
import { initPanel as initWorldPanel } from "./panels/world_panel.js";
import { initPanel as initWorldPreviewPanel } from "./panels/world_preview_panel.js";
import { initPanel as initPartyPanel } from "./panels/party_panel.js";
import { initPanel as initMapPanel } from "./panels/map_panel.js";
import { initPanel as initScenePanel } from "./panels/scene_panel.js";
import { initPanel as initStoryPanel } from "./panels/story_panel.js";
import { initPanel as initActorControlPanel } from "./panels/actor_control_panel.js";

function initStatusLine(store) {
  const statusLine = document.getElementById("statusLine");
  if (!statusLine) {
    return;
  }
  const render = () => {
    statusLine.textContent = store.getState().statusMessage || "Idle";
  };
  render();
  store.subscribe(render);
}

function startReadinessPolling(store) {
  window.setInterval(async () => {
    const state = store.getState();
    if (!state.baseUrl || state.backend?.ready !== false) {
      return;
    }
    const recovered = await store.recoverRuntime({ silent: true, manual: false });
    if (recovered) {
      store.setStatusMessage("Backend unlocked. Play page recovered.");
    }
  }, 3000);
}

async function initPlay() {
  const store = {
    getState,
    subscribe,
    setStatusMessage,
    setBaseUrl,
    setCampaignId,
    setCampaignOptions,
    setPartyActors,
    setCharacterCreateForm,
    setWorldGenerateForm,
    setSelectedItemForActor,
    setSelectedSceneTargetForActor,
    setDebugResponseText,
    recordTurnResult,
    setStateSummary,
    buildTurnContextHintsForActor,
    getSelectedItemIdForActor,
    getSelectedSceneTargetForActor,
    loadCampaignOptionsFromBackend,
    loadCharacterLibrary,
    checkBackendReady,
    recoverFrontendSession,
    createCharacter,
    generateWorldResource,
    createCampaignWithSelectedParty,
    loadCharacterToCampaign,
    refreshCampaignWorldPreview,
    refreshMapView,
    refreshWorlds,
    refreshCampaign,
    selectActiveActor,
  };

  let recoverPromise = null;
  store.refreshPlayMap = async (options = {}) => {
    const state = store.getState();
    if (!state.campaignId || !state.campaign.active_actor_id) {
      return false;
    }
    const result = await store.refreshMapView(
      state.campaignId,
      state.campaign.active_actor_id,
      state.baseUrl,
      options
    );
    return result.ok;
  };
  store.recoverRuntime = ({ silent = false, manual = false } = {}) => {
    if (recoverPromise) {
      return recoverPromise;
    }
    recoverPromise = (async () => {
      const recovered = await store.recoverFrontendSession(store.getState().baseUrl, {
        silent,
        loadCharacterLibrary: true,
      });
      if (!recovered.ok) {
        return false;
      }
      await store.refreshPlayMap({ emit: true });
      if (manual) {
        store.setStatusMessage("Backend ready. Play data reloaded.");
      }
      return true;
    })();
    recoverPromise = recoverPromise.finally(() => {
      recoverPromise = null;
    });
    return recoverPromise;
  };

  const createCampaignWithSelectedPartyBase = store.createCampaignWithSelectedParty;
  store.createCampaignWithSelectedParty = async (...args) => {
    const result = await createCampaignWithSelectedPartyBase(...args);
    if (result?.ok) {
      await store.refreshPlayMap({ emit: true });
    }
    return result;
  };

  const selectActiveActorBase = store.selectActiveActor;
  store.selectActiveActor = async (...args) => {
    const result = await selectActiveActorBase(...args);
    if (result?.ok) {
      await store.refreshPlayMap({ emit: true });
    }
    return result;
  };

  const loadCharacterToCampaignBase = store.loadCharacterToCampaign;
  store.loadCharacterToCampaign = async (...args) => {
    const result = await loadCharacterToCampaignBase(...args);
    if (result?.ok) {
      await store.refreshPlayMap({ emit: true });
    }
    return result;
  };

  initializeStore();
  initStatusLine(store);
  initCampaignPanel(store);
  initWorldPanel(store);
  initWorldPreviewPanel(store);
  initCharacterLibraryPanel(store);
  initPartyPanel(store);
  initStoryPanel(store);
  initScenePanel(store);
  initMapPanel(store);
  initActorControlPanel(store);
  startReadinessPolling(store);
  if (store.getState().baseUrl) {
    const recovered = await store.recoverRuntime({ silent: false, manual: false });
    if (!recovered && store.getState().backend.ready !== false) {
      store.setStatusMessage("Play page ready.");
    }
  } else {
    store.setStatusMessage("Play page ready.");
  }
}

void initPlay();
