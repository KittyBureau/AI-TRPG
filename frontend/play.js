import {
  createCharacter,
  getState,
  initializeStore,
  loadCharacterLibrary,
  loadCharacterToCampaign,
  refreshCampaign,
  selectActiveActor,
  setBaseUrl,
  setCampaignId,
  setCampaignOptions,
  setCharacterCreateForm,
  setDebugResponseText,
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

function initPlay() {
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
    setStateSummary,
    setMapView,
    loadCharacterLibrary,
    createCharacter,
    loadCharacterToCampaign,
    refreshCampaign,
    selectActiveActor,
  };

  initializeStore();
  initStatusLine(store);
  initCampaignPanel(store);
  initCharacterLibraryPanel(store);
  initPartyPanel(store);
  initActorControlPanel(store);
  initDebugPanel(store);
  store.setStatusMessage("Play page ready.");
}

initPlay();
