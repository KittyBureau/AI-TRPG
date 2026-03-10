import { resolveActingActorId } from "../utils/acting_actor.js";

function normalizeString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
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
  const canEnhanceCurrentArea =
    Boolean(summary) && summaryActorId === activeActorId && summaryAreaId === currentAreaId;
  const currentArea = {
    id: currentAreaId || normalizeString(baseArea?.id),
    name:
      (canEnhanceCurrentArea && normalizeString(summary?.active_area_name)) ||
      normalizeString(baseArea?.name),
    description:
      (canEnhanceCurrentArea && normalizeString(summary?.active_area_description)) ||
      normalizeString(baseArea?.description),
    reachable_area_ids: Array.isArray(baseArea?.reachable_area_ids)
      ? baseArea.reachable_area_ids
          .map((areaId) => normalizeString(areaId))
          .filter(Boolean)
      : [],
  };
  const reachableAreas = currentArea.reachable_area_ids.map((areaId) => {
    const area =
      mapAreas[areaId] && typeof mapAreas[areaId] === "object" ? mapAreas[areaId] : null;
    return {
      id: areaId,
      name: normalizeString(area?.name),
      description: normalizeString(area?.description),
    };
  });

  return {
    activeActorId,
    hasActorSnapshot: Boolean(activeActor),
    currentArea,
    hasCurrentAreaSnapshot: Boolean(baseArea),
    reachableAreas,
  };
}

export function initPanel(store) {
  const mount = document.getElementById("mapPanel");
  if (!mount) {
    return;
  }

  function render() {
    const view = deriveMapPanelView(store.getState());
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Map";
    mount.appendChild(title);

    const actorRow = document.createElement("div");
    actorRow.className = "row";
    actorRow.textContent = `Active actor: ${view.activeActorId || "none"}`;
    mount.appendChild(actorRow);

    if (!view.activeActorId) {
      const empty = document.createElement("div");
      empty.className = "note";
      empty.textContent = "Select or load a campaign actor to inspect the current area.";
      mount.appendChild(empty);
      return;
    }

    if (!view.hasActorSnapshot) {
      const actorMissing = document.createElement("div");
      actorMissing.className = "note";
      actorMissing.textContent =
        "Actor snapshot unavailable in the current campaign refresh. Refresh the campaign to reload authoritative map state.";
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
    } else if (view.currentArea.id) {
      const noDescription = document.createElement("div");
      noDescription.className = "note";
      noDescription.textContent = "Current area description unavailable.";
      mount.appendChild(noDescription);
    }

    if (!view.currentArea.id) {
      const missingArea = document.createElement("div");
      missingArea.className = "note";
      missingArea.textContent = "Active actor position is not set.";
      mount.appendChild(missingArea);
      return;
    }

    if (!view.hasCurrentAreaSnapshot) {
      const mapMissing = document.createElement("div");
      mapMissing.className = "note";
      mapMissing.textContent =
        "Current area exists on the actor snapshot, but the matching area entry is missing from the campaign map.";
      mount.appendChild(mapMissing);
      return;
    }

    const reachableTitle = document.createElement("div");
    reachableTitle.className = "note";
    reachableTitle.textContent = `Reachable areas (${view.reachableAreas.length})`;
    mount.appendChild(reachableTitle);

    const reachableList = document.createElement("div");
    reachableList.className = "stack";
    if (!view.reachableAreas.length) {
      const none = document.createElement("div");
      none.className = "row note";
      none.textContent = "(none)";
      reachableList.appendChild(none);
    } else {
      for (const area of view.reachableAreas) {
        const row = document.createElement("div");
        row.className = "row";
        row.textContent = formatAreaLabel(area);
        reachableList.appendChild(row);
      }
    }
    mount.appendChild(reachableList);
  }

  render();
  store.subscribe(render);
}
