function normalizeBaseUrl(raw) {
  return (raw || "").trim().replace(/\/+$/, "");
}

function buildUrl(baseUrl, path) {
  const normalized = normalizeBaseUrl(baseUrl);
  return `${normalized}${path}`;
}

async function request(baseUrl, path, options = {}) {
  const response = await fetch(buildUrl(baseUrl, path), options);
  const text = await response.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (_error) {
    data = null;
  }
  return {
    ok: response.ok,
    status: response.status,
    data,
    text,
  };
}

export async function listCampaigns(baseUrl) {
  return request(baseUrl, "/api/v1/campaign/list");
}

export async function createCampaign(baseUrl, payload = {}) {
  return request(baseUrl, "/api/v1/campaign/create", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function chatTurn(baseUrl, payload) {
  return request(baseUrl, "/api/v1/chat/turn", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getMapView(baseUrl, campaignId, actorId = null) {
  if (!campaignId) {
    return {
      ok: false,
      status: 400,
      data: null,
      text: "campaign_id is required",
    };
  }
  const params = new URLSearchParams({ campaign_id: campaignId });
  if (actorId) {
    params.set("actor_id", actorId);
  }
  return request(baseUrl, `/api/v1/map/view?${params.toString()}`);
}

export async function listCharacters(baseUrl) {
  return request(baseUrl, "/api/v1/characters/library");
}

export async function createCharacter(baseUrl, payload) {
  return request(baseUrl, "/api/v1/characters/library", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
}

export async function loadCharacterToCampaign(baseUrl, campaignId, characterId) {
  if (!campaignId) {
    return {
      ok: false,
      status: 400,
      data: null,
      text: "campaign_id is required",
    };
  }
  if (!characterId) {
    return {
      ok: false,
      status: 400,
      data: null,
      text: "character_id is required",
    };
  }
  return request(
    baseUrl,
    `/api/v1/campaigns/${encodeURIComponent(campaignId)}/party/load`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ character_id: characterId }),
    }
  );
}

export async function selectActor(baseUrl, campaignId, activeActorId) {
  if (!campaignId) {
    return {
      ok: false,
      status: 400,
      data: null,
      text: "campaign_id is required",
    };
  }
  if (!activeActorId) {
    return {
      ok: false,
      status: 400,
      data: null,
      text: "active_actor_id is required",
    };
  }
  return request(baseUrl, "/api/v1/campaign/select_actor", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      campaign_id: campaignId,
      active_actor_id: activeActorId,
    }),
  });
}
