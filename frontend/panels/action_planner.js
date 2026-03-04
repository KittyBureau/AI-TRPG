import { chatTurn, getMapView } from "../api/api.js";
import { createLogEntry } from "../models/log_entry.js";
import { buildDelta, buildErrorDelta } from "../renderers/delta_renderer.js";
import {
  addPlannedAction,
  appendTurnHistory,
  beginRound,
  clearPlannedActions,
  finishRound,
  getState,
  removePlannedAction,
  setFailurePolicy,
  setInitiativeOrder,
  setMapView,
  setPlannerActorId,
  setStateSummary,
} from "../store/store.js";

function moveActor(order, actorId, direction) {
  const currentIndex = order.indexOf(actorId);
  if (currentIndex < 0) {
    return order;
  }
  const nextIndex = currentIndex + direction;
  if (nextIndex < 0 || nextIndex >= order.length) {
    return order;
  }
  const next = [...order];
  const temp = next[currentIndex];
  next[currentIndex] = next[nextIndex];
  next[nextIndex] = temp;
  return next;
}

async function loadMapForActor(baseUrl, campaignId, actorId) {
  const mapResult = await getMapView(baseUrl, campaignId, actorId);
  if (mapResult.ok && mapResult.data) {
    setMapView(mapResult.data);
  }
}

function buildStrictPrompt(envelope) {
  if (envelope.type === "move") {
    const args = {
      actor_id: envelope.actor_id,
      to_area_id: envelope.to_area_id,
    };
    return `[UI_FLOW_STEP]
Return JSON with keys assistant_text, dialog_type, tool_calls.
Keep assistant_text empty.
Execute exactly one tool_call now: move.
Use args exactly:
${JSON.stringify(args)}
Do not call any additional tools.`;
  }
  const args = {
    actor_id: envelope.actor_id,
    action: envelope.action,
    target_id: envelope.target_id,
    params: envelope.params && typeof envelope.params === "object" ? envelope.params : {},
  };
  return `[UI_FLOW_STEP]
Return JSON with keys assistant_text, dialog_type, tool_calls.
Keep assistant_text empty.
Execute exactly one tool_call now: scene_action.
Use args exactly:
${JSON.stringify(args)}
Do not call any additional tools.`;
}

function buildTurnPayload(campaignId, envelope) {
  return {
    campaign_id: campaignId,
    user_input: buildStrictPrompt(envelope),
    execution: { actor_id: envelope.actor_id },
  };
}

function sceneActionLabel(action) {
  if (!action || typeof action !== "string") {
    return "Scene Action";
  }
  return `${action.slice(0, 1).toUpperCase()}${action.slice(1)}`;
}

function plannedActionSummary(envelope) {
  if (!envelope || typeof envelope !== "object") {
    return "Invalid action";
  }
  if (envelope.type === "move") {
    const label = envelope.to_area_name ? `${envelope.to_area_name} (${envelope.to_area_id})` : envelope.to_area_id;
    return `Move -> ${label}`;
  }
  if (envelope.type === "scene_action") {
    const target = envelope.target_label
      ? `${envelope.target_label} (${envelope.target_id})`
      : envelope.target_id;
    return `${sceneActionLabel(envelope.action)} -> ${target}`;
  }
  return envelope.type;
}

function extractStepNarrative(responseData) {
  if (responseData && typeof responseData.narrative_text === "string" && responseData.narrative_text.trim()) {
    return responseData.narrative_text;
  }
  const applied = Array.isArray(responseData?.applied_actions) ? responseData.applied_actions : [];
  const first = applied[0];
  const toolNarrative = first?.result?.narrative;
  if (typeof toolNarrative === "string" && toolNarrative.trim()) {
    return toolNarrative;
  }
  return "(no narrative)";
}

export async function runRound(context) {
  const state = getState();
  if (!state.campaignId) {
    context.setStatus("Select a campaign first.");
    return;
  }
  if (!state.initiativeOrder.length) {
    context.setStatus("Configure party actors first.");
    return;
  }

  const round = beginRound();
  context.setStatus(`Running round ${round} ...`);

  let previousSummary = state.stateSummary;
  let executedSteps = 0;

  for (const actorId of state.initiativeOrder) {
    const latestState = getState();
    const queued = Array.isArray(latestState.plannedActions?.[actorId])
      ? [...latestState.plannedActions[actorId]]
      : [];

    if (!queued.length) {
      appendTurnHistory(
        createLogEntry({
          round,
          actor: actorId,
          narrative: "No planned actions.",
          delta: buildErrorDelta(previousSummary, actorId, "skipped", "No planned actions."),
          status: "skipped",
          raw: null,
        })
      );
      continue;
    }

    for (const envelope of queued) {
      removePlannedAction(actorId, 0);
      const payload = buildTurnPayload(latestState.campaignId, envelope);
      const result = await chatTurn(latestState.baseUrl, payload);
      executedSteps += 1;

      if (!result.ok || !result.data) {
        appendTurnHistory(
          createLogEntry({
            round,
            actor: actorId,
            narrative: `${plannedActionSummary(envelope)} failed: ${result.text || `HTTP ${result.status}`}`,
            delta: buildErrorDelta(
              previousSummary,
              actorId,
              "request_failed",
              result.text || `HTTP ${result.status}`,
              result.status
            ),
            status: "error",
            raw: {
              request: payload,
              response: result.data,
              status: result.status,
              text: result.text,
            },
          })
        );
        if (latestState.failurePolicy === "stop") {
          finishRound();
          context.setStatus(`Round ${round} stopped on ${actorId} (${result.status}).`);
          return;
        }
        continue;
      }

      if (result.data.effective_actor_id !== actorId) {
        appendTurnHistory(
          createLogEntry({
            round,
            actor: actorId,
            narrative: `${plannedActionSummary(envelope)} failed: effective_actor_id mismatch.`,
            delta: buildErrorDelta(
              previousSummary,
              actorId,
              "actor_context_mismatch",
              `expected=${actorId}, got=${String(result.data.effective_actor_id)}`,
              result.status
            ),
            status: "error",
            raw: {
              request: payload,
              response: result.data,
              status: result.status,
            },
          })
        );
        if (latestState.failurePolicy === "stop") {
          finishRound();
          context.setStatus(`Round ${round} stopped on ${actorId} (actor mismatch).`);
          return;
        }
        continue;
      }

      const nextSummary = result.data.state_summary || null;
      const delta = buildDelta(previousSummary, nextSummary, actorId);
      appendTurnHistory(
        createLogEntry({
          round,
          actor: actorId,
          narrative: `${plannedActionSummary(envelope)} | ${extractStepNarrative(result.data)}`,
          delta,
          status: "ok",
          raw: {
            request: payload,
            response: result.data,
            status: result.status,
          },
        })
      );

      setStateSummary(nextSummary);
      previousSummary = nextSummary;
      await loadMapForActor(latestState.baseUrl, latestState.campaignId, actorId);
    }
  }

  finishRound();
  if (executedSteps === 0) {
    context.setStatus(`Round ${round} complete (no queued actions).`);
    return;
  }
  context.setStatus(`Round ${round} complete (${executedSteps} step(s)).`);
}

export function renderActionPlannerPanel(body, state, context) {
  const failureField = document.createElement("label");
  failureField.className = "field";
  failureField.innerHTML = '<span class="field-label">Failure policy</span>';
  const failureSelect = document.createElement("select");
  const stopOption = document.createElement("option");
  stopOption.value = "stop";
  stopOption.textContent = "stop";
  const continueOption = document.createElement("option");
  continueOption.value = "continue";
  continueOption.textContent = "continue";
  failureSelect.appendChild(stopOption);
  failureSelect.appendChild(continueOption);
  failureSelect.value = state.failurePolicy || "stop";
  failureSelect.addEventListener("change", () => {
    setFailurePolicy(failureSelect.value);
  });
  failureField.appendChild(failureSelect);
  body.appendChild(failureField);

  const plannerField = document.createElement("label");
  plannerField.className = "field";
  plannerField.innerHTML = '<span class="field-label">Planner Actor</span>';
  const plannerSelect = document.createElement("select");
  const plannerActors = state.initiativeOrder.length ? state.initiativeOrder : state.partyActors;
  for (const actorId of plannerActors) {
    const option = document.createElement("option");
    option.value = actorId;
    option.textContent = actorId;
    option.selected = actorId === state.plannerActorId;
    plannerSelect.appendChild(option);
  }
  plannerSelect.addEventListener("change", () => {
    setPlannerActorId(plannerSelect.value);
  });
  plannerField.appendChild(plannerSelect);
  body.appendChild(plannerField);

  const moveField = document.createElement("label");
  moveField.className = "field";
  moveField.innerHTML = '<span class="field-label">Add Move Action</span>';
  const moveControls = document.createElement("div");
  moveControls.className = "inline";
  const moveSelect = document.createElement("select");
  const reachable = Array.isArray(state.mapView?.reachable_areas) ? state.mapView.reachable_areas : [];
  const blankOption = document.createElement("option");
  blankOption.value = "";
  blankOption.textContent = "Select reachable area";
  moveSelect.appendChild(blankOption);
  for (const area of reachable) {
    const option = document.createElement("option");
    option.value = area.id;
    option.textContent = `${area.name} (${area.id})`;
    moveSelect.appendChild(option);
  }
  const moveInput = document.createElement("input");
  moveInput.placeholder = "to_area_id";
  moveSelect.addEventListener("change", () => {
    moveInput.value = moveSelect.value || "";
  });
  const addMoveButton = document.createElement("button");
  addMoveButton.className = "ghost";
  addMoveButton.textContent = "Add Move";
  addMoveButton.addEventListener("click", () => {
    const actorId = plannerSelect.value || state.plannerActorId;
    const toAreaId = (moveInput.value || "").trim();
    if (!actorId || !toAreaId) {
      context.setStatus("Planner actor and to_area_id are required for move.");
      return;
    }
    const selectedArea = reachable.find((area) => area.id === toAreaId);
    const ok = addPlannedAction({
      type: "move",
      actor_id: actorId,
      to_area_id: toAreaId,
      to_area_name: selectedArea?.name || "",
    });
    if (!ok) {
      context.setStatus("Failed to add move action.");
      return;
    }
    moveInput.value = "";
    moveSelect.value = "";
    context.setStatus(`Added move action for ${actorId}.`);
  });
  moveControls.appendChild(moveSelect);
  moveControls.appendChild(moveInput);
  moveControls.appendChild(addMoveButton);
  moveField.appendChild(moveControls);
  body.appendChild(moveField);

  const reorderHint = document.createElement("div");
  reorderHint.className = "note";
  reorderHint.textContent = "Initiative order defines execution order.";
  body.appendChild(reorderHint);

  const list = document.createElement("div");
  list.className = "stack";
  if (state.initiativeOrder.length === 0) {
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "No initiative order yet.";
    list.appendChild(note);
  } else {
    state.initiativeOrder.forEach((actorId, index) => {
      const row = document.createElement("div");
      row.className = "actor-row";

      const header = document.createElement("div");
      header.className = "actor-header";
      const title = document.createElement("strong");
      title.textContent = `${index + 1}. ${actorId}`;
      const controls = document.createElement("div");
      controls.className = "inline";
      const up = document.createElement("button");
      up.className = "ghost";
      up.textContent = "Up";
      up.addEventListener("click", () => {
        setInitiativeOrder(moveActor(state.initiativeOrder, actorId, -1));
      });
      const down = document.createElement("button");
      down.className = "ghost";
      down.textContent = "Down";
      down.addEventListener("click", () => {
        setInitiativeOrder(moveActor(state.initiativeOrder, actorId, 1));
      });
      const clearButton = document.createElement("button");
      clearButton.className = "ghost";
      clearButton.textContent = "Clear";
      clearButton.addEventListener("click", () => {
        clearPlannedActions(actorId);
      });
      controls.appendChild(up);
      controls.appendChild(down);
      controls.appendChild(clearButton);
      header.appendChild(title);
      header.appendChild(controls);

      row.appendChild(header);
      const actionList = document.createElement("div");
      actionList.className = "stack";
      const actions = Array.isArray(state.plannedActions?.[actorId]) ? state.plannedActions[actorId] : [];
      if (!actions.length) {
        const empty = document.createElement("div");
        empty.className = "note";
        empty.textContent = "No planned actions.";
        actionList.appendChild(empty);
      } else {
        actions.forEach((envelope, actionIndex) => {
          const actionRow = document.createElement("div");
          actionRow.className = "state-card";
          const summary = document.createElement("div");
          summary.textContent = `${actionIndex + 1}. ${plannedActionSummary(envelope)}`;
          const removeButton = document.createElement("button");
          removeButton.className = "ghost";
          removeButton.textContent = "Remove";
          removeButton.addEventListener("click", () => {
            removePlannedAction(actorId, actionIndex);
          });
          actionRow.appendChild(summary);
          actionRow.appendChild(removeButton);
          actionList.appendChild(actionRow);
        });
      }
      row.appendChild(actionList);
      list.appendChild(row);
    });
  }

  const runButton = document.createElement("button");
  runButton.textContent = state.roundState === "running" ? "Running..." : "Run Round";
  runButton.disabled = state.roundState === "running";
  runButton.addEventListener("click", () => {
    runRound(context);
  });

  const clearAllButton = document.createElement("button");
  clearAllButton.className = "ghost";
  clearAllButton.textContent = "Clear All Actions";
  clearAllButton.addEventListener("click", () => {
    clearPlannedActions();
  });

  body.appendChild(list);
  body.appendChild(runButton);
  body.appendChild(clearAllButton);
}
