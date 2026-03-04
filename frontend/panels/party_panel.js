function parseActorIds(raw) {
  const tokens = (raw || "")
    .split(/[\n,]/)
    .map((token) => token.trim())
    .filter(Boolean);
  return [...new Set(tokens)];
}

export function renderCampaignPanel(body, state, context) {
  const baseField = document.createElement("label");
  baseField.className = "field";
  baseField.innerHTML = '<span class="field-label">Base URL</span>';
  const baseInput = document.createElement("input");
  baseInput.placeholder = "http://127.0.0.1:8000";
  baseInput.value = state.baseUrl || "";
  baseInput.addEventListener("change", () => {
    context.setBaseUrl(baseInput.value);
  });
  baseField.appendChild(baseInput);

  const campaignField = document.createElement("label");
  campaignField.className = "field";
  campaignField.innerHTML = '<span class="field-label">Campaign</span>';
  const campaignControls = document.createElement("div");
  campaignControls.className = "inline";

  const campaignSelect = document.createElement("select");
  campaignSelect.addEventListener("change", () => {
    context.setCampaignId(campaignSelect.value);
  });
  const empty = document.createElement("option");
  empty.value = "";
  empty.textContent = "Select campaign";
  campaignSelect.appendChild(empty);
  for (const campaign of state.campaignOptions) {
    const option = document.createElement("option");
    option.value = campaign.id;
    option.textContent = `${campaign.id} (active=${campaign.active_actor_id})`;
    option.selected = campaign.id === state.campaignId;
    campaignSelect.appendChild(option);
  }

  const refreshButton = document.createElement("button");
  refreshButton.className = "ghost";
  refreshButton.textContent = "Refresh";
  refreshButton.addEventListener("click", context.refreshCampaigns);

  const createButton = document.createElement("button");
  createButton.textContent = "Create Campaign";
  createButton.addEventListener("click", context.createCampaign);

  campaignControls.appendChild(campaignSelect);
  campaignControls.appendChild(refreshButton);
  campaignControls.appendChild(createButton);
  campaignField.appendChild(campaignControls);

  const status = document.createElement("div");
  status.className = "note";
  status.textContent = `Round: ${state.roundState} | Campaign: ${state.campaignId || "none"}`;

  body.appendChild(baseField);
  body.appendChild(campaignField);
  body.appendChild(status);
}

export function renderPartyPanel(body, state, context) {
  const actorInputField = document.createElement("label");
  actorInputField.className = "field";
  actorInputField.innerHTML = '<span class="field-label">Party Actors (CSV or newline)</span>';
  const actorInput = document.createElement("textarea");
  actorInput.rows = 4;
  actorInput.value = state.partyActors.join(", ");
  actorInputField.appendChild(actorInput);

  const controls = document.createElement("div");
  controls.className = "inline";

  const applyButton = document.createElement("button");
  applyButton.textContent = "Apply Actors";
  applyButton.addEventListener("click", () => {
    context.setPartyActors(parseActorIds(actorInput.value));
  });

  const fromSummaryButton = document.createElement("button");
  fromSummaryButton.className = "ghost";
  fromSummaryButton.textContent = "Use Summary Actors";
  fromSummaryButton.addEventListener("click", context.setPartyFromSummary);

  controls.appendChild(applyButton);
  controls.appendChild(fromSummaryButton);

  const actorList = document.createElement("div");
  actorList.className = "stack";
  if (state.partyActors.length === 0) {
    const note = document.createElement("div");
    note.className = "note";
    note.textContent = "No party actors configured.";
    actorList.appendChild(note);
  } else {
    for (const actorId of state.partyActors) {
      const row = document.createElement("div");
      row.className = "state-card";
      row.textContent = actorId;
      actorList.appendChild(row);
    }
  }

  body.appendChild(actorInputField);
  body.appendChild(controls);
  body.appendChild(actorList);
}
