import { chatTurn, getMapView } from "../api/api.js";
import { createLogEntry } from "../models/log_entry.js";
import { buildDelta, buildErrorDelta } from "../renderers/delta_renderer.js";
import {
  appendTurnHistory,
  beginRound,
  finishRound,
  getState,
  setActionInput,
  setFailurePolicy,
  setInitiativeOrder,
  setMapView,
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

  for (const actorId of state.initiativeOrder) {
    const latestState = getState();
    const actionText = (latestState.actionInputs[actorId] || "").trim();

    if (!actionText) {
      appendTurnHistory(
        createLogEntry({
          round,
          actor: actorId,
          narrative: "No action input provided.",
          delta: buildErrorDelta(previousSummary, actorId, "skipped", "No action input provided."),
          status: "skipped",
          raw: null,
        })
      );
      continue;
    }

    const payload = {
      campaign_id: latestState.campaignId,
      user_input: actionText,
      execution: { actor_id: actorId },
    };

    const result = await chatTurn(latestState.baseUrl, payload);
    if (!result.ok || !result.data) {
      appendTurnHistory(
        createLogEntry({
          round,
          actor: actorId,
          narrative: result.text || `HTTP ${result.status}`,
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
          narrative: "effective_actor_id mismatch.",
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
        narrative: result.data.narrative_text || "",
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

  finishRound();
  context.setStatus(`Round ${round} complete.`);
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
      controls.appendChild(up);
      controls.appendChild(down);
      header.appendChild(title);
      header.appendChild(controls);

      const input = document.createElement("textarea");
      input.rows = 3;
      input.value = state.actionInputs[actorId] || "";
      input.placeholder = "Action for this actor";
      input.addEventListener("input", () => {
        setActionInput(actorId, input.value, { emit: false });
      });

      row.appendChild(header);
      row.appendChild(input);
      list.appendChild(row);
    });
  }

  const runButton = document.createElement("button");
  runButton.textContent = state.roundState === "running" ? "Running..." : "Run Round";
  runButton.disabled = state.roundState === "running";
  runButton.addEventListener("click", () => {
    runRound(context);
  });

  body.appendChild(list);
  body.appendChild(runButton);
}
