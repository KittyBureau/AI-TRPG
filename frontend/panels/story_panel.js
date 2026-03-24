function normalizeString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function latestTurn(state) {
  return Array.isArray(state?.turnHistory) && state.turnHistory.length
    ? state.turnHistory[state.turnHistory.length - 1]
    : null;
}

function latestNarrative(state) {
  const turn = latestTurn(state);
  const narrative = normalizeString(turn?.raw?.narrative_text);
  if (narrative) {
    return narrative;
  }
  const summary =
    state?.stateSummary && typeof state.stateSummary === "object" ? state.stateSummary : null;
  const activeAreaName = normalizeString(summary?.active_area_name);
  const activeAreaDescription = normalizeString(summary?.active_area_description);
  const latestAction = Array.isArray(turn?.applied_actions) && turn.applied_actions.length
    ? turn.applied_actions[turn.applied_actions.length - 1]
    : null;
  if (latestAction?.tool === "move" && activeAreaName) {
    return activeAreaDescription
      ? `You arrive at ${activeAreaName}. ${activeAreaDescription}`
      : `You arrive at ${activeAreaName}.`;
  }
  if (activeAreaDescription) {
    return activeAreaDescription;
  }
  return "No narrative yet. Start the scenario or send a turn.";
}

function latestResultHint(state) {
  const turn = latestTurn(state);
  const failedCalls = Array.isArray(turn?.tool_feedback?.failed_calls)
    ? turn.tool_feedback.failed_calls
    : [];
  if (failedCalls.length) {
    return failedCalls
      .map((item) => `${normalizeString(item.tool) || "tool"}: ${normalizeString(item.reason) || "failed"}`)
      .join(" | ");
  }
  const latestAction = Array.isArray(turn?.applied_actions) && turn.applied_actions.length
    ? turn.applied_actions[turn.applied_actions.length - 1]
    : null;
  const actionTool = normalizeString(latestAction?.tool);
  if (actionTool) {
    return `Latest action: ${actionTool}`;
  }
  return normalizeString(state?.statusMessage) || "Idle";
}

function recentHistory(state) {
  if (!Array.isArray(state?.turnHistory)) {
    return [];
  }
  return state.turnHistory
    .slice(-3)
    .reverse()
    .map((turn) => {
      const text = normalizeString(turn?.raw?.narrative_text);
      const toolNames = Array.isArray(turn?.applied_actions)
        ? turn.applied_actions
            .map((action) => normalizeString(action?.tool))
            .filter(Boolean)
            .join(", ")
        : "";
      return {
        narrative: text || "No narrative text.",
        tools: toolNames || "no tools",
      };
    });
}

export function deriveStoryPanelView(state) {
  const summary =
    state?.stateSummary && typeof state.stateSummary === "object" ? state.stateSummary : null;
  return {
    objective: normalizeString(summary?.objective),
    narrative: latestNarrative(state),
    resultHint: latestResultHint(state),
    history: recentHistory(state),
  };
}

export function initPanel(store) {
  const mount = document.getElementById("storyPanel");
  if (!mount) {
    return;
  }

  function render() {
    const view = deriveStoryPanelView(store.getState());
    mount.innerHTML = "";

    const title = document.createElement("h2");
    title.className = "panel-title";
    title.textContent = "Narrative";
    mount.appendChild(title);

    if (view.objective) {
      const objective = document.createElement("div");
      objective.className = "story-objective";
      objective.textContent = `Objective: ${view.objective}`;
      mount.appendChild(objective);
    }

    const narrative = document.createElement("div");
    narrative.className = "story-text";
    narrative.textContent = view.narrative;
    mount.appendChild(narrative);

    const result = document.createElement("div");
    result.className = "story-result";
    result.textContent = view.resultHint;
    mount.appendChild(result);

    const historyTitle = document.createElement("div");
    historyTitle.className = "note";
    historyTitle.textContent = "Recent turns";
    mount.appendChild(historyTitle);

    const historyList = document.createElement("div");
    historyList.className = "stack";
    for (const entry of view.history) {
      const card = document.createElement("div");
      card.className = "story-history-entry";
      const text = document.createElement("div");
      text.textContent = entry.narrative;
      const meta = document.createElement("div");
      meta.className = "story-history-meta";
      meta.textContent = entry.tools;
      card.appendChild(text);
      card.appendChild(meta);
      historyList.appendChild(card);
    }
    mount.appendChild(historyList);
  }

  render();
  store.subscribe(render);
}
