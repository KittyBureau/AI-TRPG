export function initPanel(store) {
  const mount = document.getElementById("partyPanel");
  if (!mount) {
    return;
  }

  function render() {
    const state = store.getState();
    const party = Array.isArray(state.campaign?.party_character_ids)
      ? state.campaign.party_character_ids
      : Array.isArray(state.partyActors)
        ? state.partyActors
        : [];
    const activeActorId = state.campaign?.active_actor_id || "";

    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Party";
    mount.appendChild(title);

    const active = document.createElement("div");
    active.className = "row";
    active.textContent = `active_actor_id: ${activeActorId || "none"}`;
    mount.appendChild(active);

    const listTitle = document.createElement("div");
    listTitle.className = "note";
    listTitle.textContent = "party_character_ids";
    mount.appendChild(listTitle);

    const list = document.createElement("div");
    list.className = "stack";
    if (!party.length) {
      const empty = document.createElement("div");
      empty.className = "row note";
      empty.textContent = "No party actors.";
      list.appendChild(empty);
    } else {
      for (const actorId of party) {
        const row = document.createElement("div");
        row.className = "row";
        row.textContent = actorId;
        list.appendChild(row);
      }
    }
    mount.appendChild(list);
  }

  render();
  store.subscribe(render);
}
