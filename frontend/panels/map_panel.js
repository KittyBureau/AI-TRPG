import { chatTurn } from "../api/api.js";
import { resolveActingActorId } from "../utils/acting_actor.js";
import { deriveSceneEntityFlags } from "../utils/scene_targets.js";

function normalizeString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function buildMovePrompt(actorId, toAreaId) {
  return `[UI_FLOW_STEP]
Return JSON with keys assistant_text, dialog_type, tool_calls.
Keep assistant_text empty.
Execute exactly one tool_call now: move.
Use args exactly:
${JSON.stringify({ actor_id: actorId, to_area_id: toAreaId })}
Do not call any additional tools.`;
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

function formatAreaLabel(area) {
  if (!area) {
    return "none";
  }
  const areaId = normalizeString(area.id);
  const areaName = normalizeString(area.name);
  if (areaName && areaId) {
    return `${areaName} (${areaId})`;
  }
  return areaId || areaName || "none";
}

export function deriveMapPanelView(state) {
  const activeActorId = resolveActingActorId(state);
  const actors =
    state?.campaign?.actors && typeof state.campaign.actors === "object"
      ? state.campaign.actors
      : {};
  const mapAreas =
    state?.campaign?.map?.areas && typeof state.campaign.map.areas === "object"
      ? state.campaign.map.areas
      : {};
  const activeActor =
    activeActorId && actors[activeActorId] && typeof actors[activeActorId] === "object"
      ? actors[activeActorId]
      : null;
  const currentAreaId = normalizeString(activeActor?.position);
  const baseArea =
    currentAreaId && mapAreas[currentAreaId] && typeof mapAreas[currentAreaId] === "object"
      ? mapAreas[currentAreaId]
      : null;
  const summary =
    state?.stateSummary && typeof state.stateSummary === "object" ? state.stateSummary : null;
  const summaryActorId = normalizeString(summary?.active_actor_id);
  const summaryAreaId = normalizeString(summary?.active_area_id);
  const mapView =
    state?.mapView && typeof state.mapView === "object" && !Array.isArray(state.mapView)
      ? state.mapView
      : null;
  const mapMatchesActor = mapView && normalizeString(mapView.active_actor_id) === activeActorId;
  const canEnhanceCurrentArea =
    Boolean(summary) && summaryActorId === activeActorId && summaryAreaId === currentAreaId;
  const currentArea = {
    id:
      normalizeString(mapView?.current_area?.id) ||
      currentAreaId ||
      normalizeString(baseArea?.id),
    name:
      normalizeString(mapView?.current_area?.name) ||
      (canEnhanceCurrentArea ? normalizeString(summary?.active_area_name) : "") ||
      normalizeString(baseArea?.name),
    description:
      (canEnhanceCurrentArea ? normalizeString(summary?.active_area_description) : "") ||
      normalizeString(baseArea?.description),
    reachable_area_ids: mapMatchesActor
      ? Array.isArray(mapView.reachable_areas)
        ? mapView.reachable_areas.map((area) => normalizeString(area?.id)).filter(Boolean)
        : []
      : Array.isArray(baseArea?.reachable_area_ids)
        ? baseArea.reachable_area_ids.map((areaId) => normalizeString(areaId)).filter(Boolean)
        : [],
  };
  const reachableAreas = currentArea.reachable_area_ids.map((areaId) => {
    const fromMapView = mapMatchesActor && Array.isArray(mapView?.reachable_areas)
      ? mapView.reachable_areas.find((area) => normalizeString(area?.id) === areaId)
      : null;
    const area =
      mapAreas[areaId] && typeof mapAreas[areaId] === "object" ? mapAreas[areaId] : null;
    return {
      id: areaId,
      name: normalizeString(fromMapView?.name) || normalizeString(area?.name),
      description: normalizeString(area?.description),
    };
  });
  const visibleEntities = mapMatchesActor && Array.isArray(mapView?.entities_in_area)
    ? mapView.entities_in_area
    : [];
  const sceneSummary = {
    visibleCount: visibleEntities.length,
    interactableCount: visibleEntities.filter((entity) => deriveSceneEntityFlags(entity).interactable).length,
    takeableCount: visibleEntities.filter((entity) => deriveSceneEntityFlags(entity).takeable).length,
  };

  return {
    activeActorId,
    hasActorSnapshot: Boolean(activeActor),
    currentArea,
    hasCurrentAreaSnapshot: Boolean(baseArea) || Boolean(mapMatchesActor),
    reachableAreas,
    sceneSummary,
  };
}

export function initPanel(store) {
  const mount = document.getElementById("mapPanel");
  if (!mount) {
    return;
  }

  async function refreshPlayState() {
    const state = store.getState();
    if (!state.campaignId) {
      return true;
    }
    const refreshResult = await store.refreshCampaign(state.campaignId, state.baseUrl);
    if (!refreshResult.ok) {
      store.setStatusMessage(`Refresh campaign failed: ${parseApiError(refreshResult)}`);
      return false;
    }
    if (typeof store.refreshMapView === "function") {
      await store.refreshMapView(state.campaignId, store.getState().campaign.active_actor_id, state.baseUrl, {
        emit: true,
      });
    }
    return true;
  }

  async function runMove(toAreaId) {
    const state = store.getState();
    if (!state.campaignId) {
      store.setStatusMessage("Select a campaign first.");
      return;
    }
    if (state.baseUrl && typeof store.checkBackendReady === "function") {
      const readiness = await store.checkBackendReady(state.baseUrl, { silent: false });
      if (readiness.ready === false) {
        return;
      }
    }
    const actorId = resolveActingActorId(state);
    if (!actorId || !toAreaId) {
      store.setStatusMessage("No active actor or destination.");
      return;
    }
    const result = await chatTurn(state.baseUrl, {
      campaign_id: state.campaignId,
      user_input: buildMovePrompt(actorId, toAreaId),
      execution: { actor_id: actorId },
    });
    if (!result.ok || !result.data) {
      store.setStatusMessage(`Move failed: ${parseApiError(result)}`);
      store.setDebugResponseText(result.text || "");
      return;
    }
    store.recordTurnResult(result.data, JSON.stringify(result.data, null, 2));
    const refreshed = await refreshPlayState();
    if (!refreshed) {
      return;
    }
    store.setStatusMessage(`Moved to ${toAreaId}.`);
  }

  function render() {
    const view = deriveMapPanelView(store.getState());
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Navigation";
    mount.appendChild(title);

    const actorRow = document.createElement("div");
    actorRow.className = "row";
    actorRow.textContent = `Active actor: ${view.activeActorId || "none"}`;
    mount.appendChild(actorRow);

    if (!view.activeActorId) {
      const empty = document.createElement("div");
      empty.className = "note";
      empty.textContent = "Select or load a campaign actor to inspect movement options.";
      mount.appendChild(empty);
      return;
    }

    if (!view.hasActorSnapshot) {
      const actorMissing = document.createElement("div");
      actorMissing.className = "note";
      actorMissing.textContent =
        "Actor snapshot unavailable in the current campaign refresh.";
      mount.appendChild(actorMissing);
      return;
    }

    const areaRow = document.createElement("div");
    areaRow.className = "row";
    areaRow.textContent = `Current area: ${formatAreaLabel(view.currentArea)}`;
    mount.appendChild(areaRow);

    if (view.currentArea.description) {
      const description = document.createElement("div");
      description.className = "note";
      description.textContent = view.currentArea.description;
      mount.appendChild(description);
    }

    const sceneSummary = document.createElement("div");
    sceneSummary.className = "row";
    sceneSummary.textContent = `Visible here: ${view.sceneSummary.visibleCount} | Interactable: ${view.sceneSummary.interactableCount} | Takeable: ${view.sceneSummary.takeableCount}`;
    mount.appendChild(sceneSummary);

    const reachableTitle = document.createElement("div");
    reachableTitle.className = "scene-section-title";
    reachableTitle.textContent = `Reachable areas (${view.reachableAreas.length})`;
    mount.appendChild(reachableTitle);

    const reachableList = document.createElement("div");
    reachableList.className = "scene-list";
    if (!view.reachableAreas.length) {
      const none = document.createElement("div");
      none.className = "scene-card note";
      none.textContent = "(none)";
      reachableList.appendChild(none);
    } else {
      for (const area of view.reachableAreas) {
        const card = document.createElement("div");
        card.className = "scene-card";

        const header = document.createElement("div");
        header.className = "scene-card-header";
        const name = document.createElement("div");
        name.className = "scene-card-title";
        name.textContent = formatAreaLabel(area);
        header.appendChild(name);
        card.appendChild(header);

        if (area.description) {
          const description = document.createElement("div");
          description.className = "scene-card-meta";
          description.textContent = area.description;
          card.appendChild(description);
        }

        const moveButton = document.createElement("button");
        moveButton.className = "secondary";
        moveButton.textContent = "Go";
        moveButton.addEventListener("click", () => {
          void runMove(area.id);
        });
        card.appendChild(moveButton);
        reachableList.appendChild(card);
      }
    }
    mount.appendChild(reachableList);
  }

  render();
  store.subscribe(render);
}
