function toText(value, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function renderActorStateList(container, summary) {
  const actors = summary?.positions && typeof summary.positions === "object"
    ? Object.keys(summary.positions).sort()
    : [];

  if (!actors.length) {
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "No actor state summary yet.";
    container.appendChild(note);
    return;
  }

  for (const actorId of actors) {
    const card = document.createElement("div");
    card.className = "state-card";

    const hp = summary?.hp?.[actorId];
    const actorState = summary?.character_states?.[actorId];
    const position = summary?.positions?.[actorId];

    card.textContent = `${actorId} | hp=${toText(hp)} | state=${toText(actorState)} | pos=${toText(position)}`;
    container.appendChild(card);
  }
}

function resolvePlannerActor(state) {
  if (state?.plannerActorId) {
    return state.plannerActorId;
  }
  if (state?.mapView?.active_actor_id) {
    return state.mapView.active_actor_id;
  }
  if (Array.isArray(state?.initiativeOrder) && state.initiativeOrder.length) {
    return state.initiativeOrder[0];
  }
  if (Array.isArray(state?.partyActors) && state.partyActors.length) {
    return state.partyActors[0];
  }
  return null;
}

function sceneVerbLabel(verb) {
  if (!verb || typeof verb !== "string") {
    return "Action";
  }
  return `${verb.slice(0, 1).toUpperCase()}${verb.slice(1)}`;
}

function renderEntitiesSection(container, state, context) {
  const wrapper = document.createElement("div");
  wrapper.className = "stack";
  const title = document.createElement("strong");
  title.textContent = "Entities In Area";
  wrapper.appendChild(title);

  const entities = Array.isArray(state.mapView?.entities_in_area) ? state.mapView.entities_in_area : [];
  if (!entities.length) {
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "No entities in current area.";
    wrapper.appendChild(note);
    container.appendChild(wrapper);
    return;
  }

  for (const entity of entities) {
    const card = document.createElement("div");
    card.className = "state-card";

    const heading = document.createElement("div");
    heading.innerHTML = `<strong>${toText(entity.label)}</strong> <span class="note">(${toText(entity.id)})</span>`;
    card.appendChild(heading);

    const kindLine = document.createElement("div");
    kindLine.className = "note";
    const tags = Array.isArray(entity.tags) && entity.tags.length ? entity.tags.join(", ") : "none";
    kindLine.textContent = `kind=${toText(entity.kind)} | tags=${tags}`;
    card.appendChild(kindLine);

    const verbs = Array.isArray(entity.verbs) ? entity.verbs.filter((verb) => typeof verb === "string" && verb.trim()) : [];
    const controls = document.createElement("div");
    controls.className = "inline";
    if (!verbs.length) {
      const empty = document.createElement("span");
      empty.className = "note";
      empty.textContent = "No available verbs.";
      controls.appendChild(empty);
    } else {
      for (const verb of verbs) {
        const button = document.createElement("button");
        button.className = "ghost";
        button.textContent = sceneVerbLabel(verb);
        button.addEventListener("click", () => {
          const actorId = resolvePlannerActor(state);
          if (!actorId) {
            context.setStatus("No actor available for action planning.");
            return;
          }
          context.addSceneAction({
            type: "scene_action",
            actor_id: actorId,
            action: verb.trim(),
            target_id: entity.id,
            target_label: entity.label,
            params: {},
          });
        });
        controls.appendChild(button);
      }
    }
    card.appendChild(controls);
    wrapper.appendChild(card);
  }

  container.appendChild(wrapper);
}

export function renderScenePanel(body, state, context) {
  const summary = state.stateSummary;

  const objective = document.createElement("div");
  objective.className = "state-card";
  objective.innerHTML = `<strong>Objective</strong><div>${toText(summary?.objective, "No objective")}</div>`;

  const scene = document.createElement("div");
  scene.className = "state-card";
  scene.innerHTML = `
    <strong>Area</strong>
    <div>ID: ${toText(summary?.active_area_id)}</div>
    <div>Name: ${toText(summary?.active_area_name)}</div>
    <div class="note">${toText(summary?.active_area_description, "No area description")}</div>
  `;

  const actors = document.createElement("div");
  actors.className = "stack";
  renderActorStateList(actors, summary);

  body.appendChild(objective);
  body.appendChild(scene);
  renderEntitiesSection(body, state, context);
  body.appendChild(actors);
}

export function renderMapPlaceholderPanel(body, state) {
  const mapView = state.mapView;
  const card = document.createElement("div");
  card.className = "state-card";

  if (!mapView || typeof mapView !== "object") {
    card.innerHTML = "<strong>Map Placeholder</strong><div class=\"note\">No map_view loaded yet.</div>";
    body.appendChild(card);
    return;
  }

  const reachable = Array.isArray(mapView.reachable_areas)
    ? mapView.reachable_areas.map((area) => `${area.id} (${area.name})`).join(", ")
    : "-";

  card.innerHTML = `
    <strong>Map Placeholder</strong>
    <div>Current: ${toText(mapView.current_area?.id)} (${toText(mapView.current_area?.name)})</div>
    <div>Reachable: ${toText(reachable)}</div>
    <div class="note">This panel is intentionally minimal and reserved for future map UI.</div>
  `;

  body.appendChild(card);
}
