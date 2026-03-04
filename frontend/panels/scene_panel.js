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

export function renderScenePanel(body, state) {
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
