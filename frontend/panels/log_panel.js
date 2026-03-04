import { renderDeltaLines } from "../renderers/delta_renderer.js";

export function renderLogPanel(body, state) {
  if (!Array.isArray(state.turnHistory) || state.turnHistory.length === 0) {
    const empty = document.createElement("div");
    empty.className = "note";
    empty.textContent = "No turns logged yet.";
    body.appendChild(empty);
    return;
  }

  for (const entry of state.turnHistory) {
    const item = document.createElement("article");
    item.className = "log-item";

    const head = document.createElement("div");
    head.className = "log-head";
    const identity = document.createElement("strong");
    identity.textContent = `R${entry.round} | ${entry.actor}`;
    const status = document.createElement("span");
    status.className = "log-status";
    status.textContent = entry.status;
    head.appendChild(identity);
    head.appendChild(status);

    const narrative = document.createElement("p");
    narrative.className = "log-narrative";
    narrative.textContent = entry.narrative || "(empty)";

    const deltaList = document.createElement("ul");
    deltaList.className = "delta-list";
    const deltaLines = renderDeltaLines(entry.delta);
    for (const line of deltaLines) {
      const lineItem = document.createElement("li");
      lineItem.textContent = line;
      deltaList.appendChild(lineItem);
    }

    item.appendChild(head);
    item.appendChild(narrative);
    item.appendChild(deltaList);
    body.appendChild(item);
  }
}
