import {
  checkBackendReady,
  createCharacter,
  getState,
  initializeStore,
  loadCharacterLibrary,
  loadCharacterToCampaign,
  loadCampaignOptionsFromBackend,
  recoverFrontendSession,
  refreshCampaign,
  selectActiveActor,
  setBaseUrl,
  setCampaignId,
  setCampaignOptions,
  setCharacterCreateForm,
  setDebugResponseText,
  recordTurnResult,
  setMapView,
  setPartyActors,
  setStateSummary,
  setStatusMessage,
  subscribe,
} from "./store/store.js";
import { initPanel as initCampaignPanel } from "./panels/campaign_panel.js";
import { initPanel as initCharacterLibraryPanel } from "./panels/character_library_panel.js";
import { initPanel as initPartyPanel } from "./panels/party_panel.js";
import { initPanel as initActorControlPanel } from "./panels/actor_control_panel.js";
import { initPanel as initDebugPanel } from "./panels/debug_panel.js";

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
    setDebugResponseText,
    recordTurnResult,
    setStateSummary,
    setMapView,
    loadCampaignOptionsFromBackend,
    loadCharacterLibrary,
    checkBackendReady,
    recoverFrontendSession,
    createCharacter,
    loadCharacterToCampaign,
    refreshCampaign,
    selectActiveActor,
  };

  let recoverPromise = null;
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

  initializeStore();
  initStatusLine(store);
  initCampaignPanel(store);
  initCharacterLibraryPanel(store);
  initPartyPanel(store);
  initActorControlPanel(store);
  initDebugPanel(store);
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
