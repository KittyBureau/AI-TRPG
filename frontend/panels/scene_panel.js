import {
  deriveSceneAffordanceTags,
  deriveSceneEntityFlags,
} from "../utils/scene_targets.js";

function normalizeString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function isSelectableSceneTarget(entity) {
  return deriveSceneEntityFlags(entity).selectable;
}

function entityStateSummary(entity) {
  if (!entity || typeof entity !== "object") {
    return "";
  }
  const parts = [];
  if (entity.state && typeof entity.state === "object" && !Array.isArray(entity.state)) {
    if (entity.state.locked === true) {
      parts.push("locked");
    }
    if (entity.state.opened === true) {
      parts.push("opened");
    }
    if (typeof entity.state.quantity === "number") {
      parts.push(`x${entity.state.quantity}`);
    }
  }
  const verbs = Array.isArray(entity.verbs) ? entity.verbs.filter(Boolean).join(", ") : "";
  if (verbs) {
    parts.push(`verbs: ${verbs}`);
  }
  return parts.join(" | ");
}

function currentAreaDescription(state) {
  const summary =
    state?.stateSummary && typeof state.stateSummary === "object" ? state.stateSummary : null;
  const description = normalizeString(summary?.active_area_description);
  if (description) {
    return description;
  }
  const activeActorId = normalizeString(state?.campaign?.active_actor_id);
  const position = normalizeString(state?.campaign?.actors?.[activeActorId]?.position);
  const fallback = normalizeString(state?.campaign?.map?.areas?.[position]?.description);
  return fallback;
}

export function deriveScenePanelView(state) {
  const activeActorId = normalizeString(state?.campaign?.active_actor_id);
  const mapView =
    state?.mapView && typeof state.mapView === "object" && !Array.isArray(state.mapView)
      ? state.mapView
      : null;
  const mapMatchesActor = mapView && normalizeString(mapView.active_actor_id) === activeActorId;
  const entities = mapMatchesActor && Array.isArray(mapView.entities_in_area) ? mapView.entities_in_area : [];
  const enrichEntity = (entity) => ({
    ...entity,
    flags: deriveSceneEntityFlags(entity),
    affordance_tags: deriveSceneAffordanceTags(entity),
  });
  const npcs = entities.filter((entity) => entity.kind === "npc").map(enrichEntity);
  const takeables = entities
    .filter((entity) => deriveSceneEntityFlags(entity).takeable)
    .map(enrichEntity);
  const interactives = entities.filter(
    (entity) =>
      entity.kind !== "npc" &&
      !deriveSceneEntityFlags(entity).takeable &&
      deriveSceneEntityFlags(entity).interactable
  ).map(enrichEntity);
  const visibleCount = entities.length;
  const interactableCount = entities.filter((entity) => deriveSceneEntityFlags(entity).interactable).length;
  const takeableCount = entities.filter((entity) => deriveSceneEntityFlags(entity).takeable).length;
  return {
    activeActorId,
    currentAreaName: normalizeString(mapView?.current_area?.name) || "Unknown Area",
    currentAreaId: normalizeString(mapView?.current_area?.id),
    currentAreaDescription: currentAreaDescription(state),
    npcs,
    takeables,
    interactives,
    visibleCount,
    interactableCount,
    takeableCount,
    hasMapView: Boolean(mapMatchesActor),
  };
}

export function initPanel(store) {
  const mount = document.getElementById("scenePanel");
  if (!mount) {
    return;
  }

  function renderEntityList(
    titleText,
    entities,
    { selectable = false, selectedId = "" } = {}
  ) {
    const title = document.createElement("div");
    title.className = "scene-section-title";
    title.textContent = `${titleText} (${entities.length})`;
    mount.appendChild(title);

    const list = document.createElement("div");
    list.className = "scene-list";
    if (!entities.length) {
      const empty = document.createElement("div");
      empty.className = "scene-card note";
      empty.textContent = "(none)";
      list.appendChild(empty);
      mount.appendChild(list);
      return;
    }

    for (const entity of entities) {
      const canSelect = selectable && isSelectableSceneTarget(entity);
      const button = document.createElement(canSelect ? "button" : "div");
      button.className = canSelect
        ? selectedId === entity.id
          ? "scene-card scene-target selected"
          : "scene-card scene-target"
        : "scene-card";
      if (canSelect) {
        button.type = "button";
        button.setAttribute("aria-pressed", selectedId === entity.id ? "true" : "false");
        button.addEventListener("click", () => {
          const selected = store.setSelectedSceneTargetForActor(
            store.getState().campaign.active_actor_id,
            entity.id
          );
          if (!selected) {
            store.setStatusMessage(`Cannot select target: ${entity.label}`);
          }
        });
      }

      const header = document.createElement("div");
      header.className = "scene-card-header";
      const label = document.createElement("div");
      label.className = "scene-card-title";
      label.textContent = entity.label;
      header.appendChild(label);
      if (canSelect && selectedId === entity.id) {
        const badge = document.createElement("div");
        badge.className = "scene-card-badge";
        badge.textContent = "Selected";
        header.appendChild(badge);
      }
      button.appendChild(header);

      const meta = document.createElement("div");
      meta.className = "scene-card-meta";
      meta.textContent = entityStateSummary(entity);
      button.appendChild(meta);

      const affordances = Array.isArray(entity.affordance_tags) ? entity.affordance_tags : [];
      if (affordances.length) {
        const affordanceRow = document.createElement("div");
        affordanceRow.className = "scene-affordances";
        for (const tag of affordances) {
          const badge = document.createElement("span");
          badge.className =
            tag === "Visible" || tag === "Interactable" || tag === "Takeable"
              ? "scene-affordance scene-affordance-state"
              : "scene-affordance";
          badge.textContent = tag;
          affordanceRow.appendChild(badge);
        }
        button.appendChild(affordanceRow);
      }
      list.appendChild(button);
    }
    mount.appendChild(list);
  }

  function render() {
    const state = store.getState();
    const view = deriveScenePanelView(state);
    const selectedSceneTarget =
      typeof store.getSelectedSceneTargetForActor === "function"
        ? store.getSelectedSceneTargetForActor(view.activeActorId)
        : null;

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Scene";
    mount.appendChild(title);

    const area = document.createElement("div");
    area.className = "scene-area-name";
    area.textContent = view.currentAreaId
      ? `${view.currentAreaName} (${view.currentAreaId})`
      : view.currentAreaName;
    mount.appendChild(area);

    if (view.currentAreaDescription) {
      const description = document.createElement("div");
      description.className = "scene-area-description";
      description.textContent = view.currentAreaDescription;
      mount.appendChild(description);
    }

    if (!view.hasMapView) {
      const note = document.createElement("div");
      note.className = "note";
      note.textContent =
        "Scene entities are unavailable until the current area view is loaded.";
      mount.appendChild(note);
      return;
    }

    const visibilitySummary = document.createElement("div");
    visibilitySummary.className = "scene-visibility-summary";
    visibilitySummary.textContent = `Visible now: ${view.visibleCount} | Interactable: ${view.interactableCount} | Takeable: ${view.takeableCount}`;
    mount.appendChild(visibilitySummary);

    renderEntityList("NPCs", view.npcs, {
      selectable: true,
      selectedId: normalizeString(selectedSceneTarget?.id),
    });
    renderEntityList("Interactive Objects", view.interactives, {
      selectable: true,
      selectedId: normalizeString(selectedSceneTarget?.id),
    });
    renderEntityList("Takeable Items", view.takeables, {
      selectable: true,
      selectedId: normalizeString(selectedSceneTarget?.id),
    });
  }

  render();
  store.subscribe(render);
}
