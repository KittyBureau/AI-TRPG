import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

function installLocalStorage() {
  const values = new Map();
  global.localStorage = {
    getItem(key) {
      return values.has(key) ? values.get(key) : null;
    },
    setItem(key, value) {
      values.set(key, String(value));
    },
    removeItem(key) {
      values.delete(key);
    },
    clear() {
      values.clear();
    },
  };
}

async function loadStoreModule() {
  installLocalStorage();
  const modulePath = pathToFileURL(
    path.resolve("frontend/store/store.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

function jsonResponse(payload, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

test("refreshCampaign syncs party and active actor from backend authority", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/campaign\/get\?/);
    return jsonResponse({
      campaign_id: "camp_001",
      selected: {
        party_character_ids: ["pc_001", "pc_002"],
        active_actor_id: "pc_002",
      },
      actors: {
        pc_001: { position: "area_001", hp: 10, character_state: "alive" },
        pc_002: { position: "area_002", hp: 9, character_state: "alive" },
      },
      map: {
        areas: {
          area_001: {
            id: "area_001",
            name: "Camp",
            description: "A quiet camp",
            parent_area_id: null,
            reachable_area_ids: ["area_002"],
          },
          area_002: {
            id: "area_002",
            name: "Gate",
            description: "The north gate",
            parent_area_id: null,
            reachable_area_ids: [],
          },
        },
      },
      status: {
        ended: false,
        reason: null,
        ended_at: null,
        milestone: {
          current: "intro",
          last_advanced_turn: 0,
          turn_trigger_interval: 6,
          pressure: 0,
          pressure_threshold: 2,
          summary: "",
        },
      },
    });
  };

  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  const result = await store.refreshCampaign("camp_001", "http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.deepEqual(store.getState().campaign.party_character_ids, ["pc_001", "pc_002"]);
  assert.equal(store.getState().campaign.active_actor_id, "pc_002");
  assert.equal(store.getState().campaignOptions[0].active_actor_id, "pc_002");
  assert.deepEqual(store.getState().campaign.actors, {
    pc_001: { position: "area_001", hp: 10, character_state: "alive" },
    pc_002: { position: "area_002", hp: 9, character_state: "alive" },
  });
  assert.deepEqual(store.getState().campaign.map, {
    areas: {
      area_001: {
        id: "area_001",
        name: "Camp",
        description: "A quiet camp",
        parent_area_id: null,
        reachable_area_ids: ["area_002"],
      },
      area_002: {
        id: "area_002",
        name: "Gate",
        description: "The north gate",
        parent_area_id: null,
        reachable_area_ids: [],
      },
    },
  });
  assert.deepEqual(store.getState().campaign.status, {
    ended: false,
    reason: null,
    ended_at: null,
    milestone: {
      current: "intro",
      last_advanced_turn: 0,
      turn_trigger_interval: 6,
      pressure: 0,
      pressure_threshold: 2,
      summary: "",
    },
  });
});

test("refreshCampaign keeps existing state when campaign get returns a missing-campaign error", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/campaign\/get\?/);
    return jsonResponse({ detail: "Campaign not found: camp_missing" }, 404);
  };

  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  store.setCampaignId("camp_001");
  store.setPartyActors(["pc_001", "pc_002"]);
  store.getState().campaign.status = {
    ended: false,
    reason: null,
    ended_at: null,
    milestone: { current: "intro", last_advanced_turn: 0, turn_trigger_interval: 6, pressure: 0, pressure_threshold: 2, summary: "" },
  };

  const result = await store.refreshCampaign("camp_missing", "http://127.0.0.1:8000");

  assert.equal(result.ok, false);
  assert.equal(result.status, 404);
  assert.deepEqual(store.getState().campaign.party_character_ids, ["pc_001", "pc_002"]);
  assert.equal(store.getState().campaign.active_actor_id, "pc_001");
  assert.equal(store.getState().campaign.status, null);
  assert.match(store.getState().statusMessage, /Campaign not found: camp_missing/);
});

test("refreshCampaign rejects invalid authoritative payload without writing dirty state", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/campaign\/get\?/);
    return jsonResponse({
      campaign_id: "camp_001",
      selected: {
        active_actor_id: "pc_999",
      },
    });
  };

  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  store.setCampaignId("camp_001");
  store.setPartyActors(["pc_001", "pc_002"]);
  store.getState().campaign.status = {
    ended: false,
    reason: null,
    ended_at: null,
    milestone: { current: "intro", last_advanced_turn: 0, turn_trigger_interval: 6, pressure: 0, pressure_threshold: 2, summary: "" },
  };

  const result = await store.refreshCampaign("camp_001", "http://127.0.0.1:8000");

  assert.equal(result.ok, false);
  assert.equal(result.status, 200);
  assert.equal(result.data.detail, "campaign/get returned invalid payload");
  assert.deepEqual(store.getState().campaign.party_character_ids, ["pc_001", "pc_002"]);
  assert.equal(store.getState().campaign.active_actor_id, "pc_001");
  assert.equal(store.getState().campaign.status, null);
  assert.match(store.getState().statusMessage, /invalid payload/i);
});

test("refreshCampaign tolerates missing status snapshot and leaves campaign status unavailable", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/campaign\/get\?/);
    return jsonResponse({
      campaign_id: "camp_001",
      selected: {
        party_character_ids: ["pc_001"],
        active_actor_id: "pc_001",
      },
      actors: ["pc_001"],
    });
  };

  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  const result = await store.refreshCampaign("camp_001", "http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.equal(store.getState().campaign.active_actor_id, "pc_001");
  assert.equal(store.getState().campaign.status, null);
});

test("campaign switch clears stale status until the next authoritative refresh completes", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    const requestUrl = String(url);
    assert.match(requestUrl, /\/api\/v1\/campaign\/get\?/);
    if (requestUrl.includes("campaign_id=camp_001")) {
      return jsonResponse({
        campaign_id: "camp_001",
        selected: {
          party_character_ids: ["pc_001"],
          active_actor_id: "pc_001",
        },
        actors: ["pc_001"],
        status: {
          ended: false,
          reason: null,
          ended_at: null,
          milestone: {
            current: "intro",
            last_advanced_turn: 0,
            turn_trigger_interval: 6,
            pressure: 0,
            pressure_threshold: 2,
            summary: "",
          },
        },
      });
    }
    if (requestUrl.includes("campaign_id=camp_002")) {
      return jsonResponse({
        campaign_id: "camp_002",
        selected: {
          party_character_ids: ["pc_002"],
          active_actor_id: "pc_002",
        },
        actors: ["pc_002"],
        status: {
          ended: true,
          reason: "quest_resolved",
          ended_at: "2026-03-09T00:00:00Z",
          milestone: {
            current: "milestone_2",
            last_advanced_turn: 4,
            turn_trigger_interval: 6,
            pressure: 0,
            pressure_threshold: 2,
            summary: "final checkpoint reached",
          },
        },
      });
    }
    throw new Error(`unexpected fetch: ${requestUrl}`);
  };

  store.setCampaignOptions([
    { id: "camp_001", active_actor_id: "pc_001" },
    { id: "camp_002", active_actor_id: "pc_002" },
  ]);

  await store.refreshCampaign("camp_001", "http://127.0.0.1:8000");
  assert.equal(store.getState().campaign.status?.milestone.current, "intro");
  assert.deepEqual(store.getState().campaign.actors, {
    pc_001: { position: null, hp: null, character_state: "" },
  });

  store.setCampaignId("camp_002");
  assert.equal(store.getState().campaign.status, null);
  assert.deepEqual(store.getState().campaign.actors, {});
  assert.deepEqual(store.getState().campaign.map, { areas: {} });

  await store.refreshCampaign("camp_002", "http://127.0.0.1:8000");
  assert.equal(store.getState().campaign.active_actor_id, "pc_002");
  assert.deepEqual(store.getState().campaign.status, {
    ended: true,
    reason: "quest_resolved",
    ended_at: "2026-03-09T00:00:00Z",
    milestone: {
      current: "milestone_2",
      last_advanced_turn: 4,
      turn_trigger_interval: 6,
      pressure: 0,
      pressure_threshold: 2,
      summary: "final checkpoint reached",
    },
  });
});

test("selectActiveActor keeps campaign option and active actor in sync", async () => {
  const store = await loadStoreModule();
  let refreshCalls = 0;
  global.fetch = async (url, options = {}) => {
    if (String(url).endsWith("/api/v1/campaign/select_actor")) {
      const body = JSON.parse(String(options.body));
      assert.equal(body.campaign_id, "camp_001");
      assert.equal(body.active_actor_id, "pc_002");
      return jsonResponse({ active_actor_id: "pc_002" });
    }
    if (String(url).includes("/api/v1/campaign/get?")) {
      refreshCalls += 1;
      return jsonResponse({
        campaign_id: "camp_001",
        selected: {
          party_character_ids: ["pc_001", "pc_002"],
          active_actor_id: "pc_002",
        },
        actors: ["pc_001", "pc_002"],
      });
    }
    throw new Error(`unexpected fetch: ${String(url)}`);
  };

  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  store.setCampaignId("camp_001");
  store.setPartyActors(["pc_001", "pc_002"]);
  const result = await store.selectActiveActor(
    "pc_002",
    "camp_001",
    "http://127.0.0.1:8000"
  );

  assert.equal(result.ok, true);
  assert.equal(refreshCalls, 1);
  assert.equal(store.getState().campaign.active_actor_id, "pc_002");
  assert.equal(store.getState().campaignOptions[0].active_actor_id, "pc_002");
});

test("recordTurnResult stores applied_actions and effective actor for panels", async () => {
  const store = await loadStoreModule();
  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  store.setCampaignId("camp_001");

  store.recordTurnResult(
    {
      effective_actor_id: "pc_002",
      applied_actions: [
        {
          tool: "move",
          result: { from_area_id: "area_001", to_area_id: "area_002" },
        },
      ],
      state_summary: {
        active_actor_id: "pc_002",
        active_actor_inventory: { torch: 1 },
      },
    },
    "{\"ok\":true}"
  );

  const state = store.getState();
  assert.equal(state.campaign.active_actor_id, "pc_002");
  assert.equal(state.campaignOptions[0].active_actor_id, "pc_002");
  assert.equal(state.turnHistory.length, 1);
  assert.deepEqual(state.turnHistory[0].applied_actions, [
    {
      tool: "move",
      result: { from_area_id: "area_001", to_area_id: "area_002" },
    },
  ]);
  assert.deepEqual(state.stateSummary, {
    active_actor_id: "pc_002",
    active_actor_inventory: { torch: 1 },
  });
  assert.equal(state.debug.responseText, "{\"ok\":true}");
});

test("selected item state stays isolated by actor and follows active actor switching", async () => {
  const store = await loadStoreModule();
  let refreshCalls = 0;
  global.fetch = async (url, options = {}) => {
    if (String(url).endsWith("/api/v1/campaign/select_actor")) {
      const body = JSON.parse(String(options.body));
      return jsonResponse({ active_actor_id: body.active_actor_id });
    }
    if (String(url).includes("/api/v1/campaign/get?")) {
      refreshCalls += 1;
      const activeActorId = refreshCalls === 1 ? "pc_002" : "pc_001";
      return jsonResponse({
        campaign_id: "camp_001",
        selected: {
          party_character_ids: ["pc_001", "pc_002"],
          active_actor_id: activeActorId,
        },
        actors: ["pc_001", "pc_002"],
      });
    }
    throw new Error(`unexpected fetch: ${String(url)}`);
  };

  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  store.setCampaignId("camp_001");
  store.setPartyActors(["pc_001", "pc_002"]);
  store.recordTurnResult({
    effective_actor_id: "pc_001",
    state_summary: {
      active_actor_id: "pc_001",
      inventories: {
        pc_001: { torch: 1, rope: 1 },
        pc_002: { potion: 2 },
      },
    },
  });

  assert.equal(store.setSelectedItemForActor("pc_001", "torch"), true);
  assert.equal(store.setSelectedItemForActor("pc_002", "potion"), true);
  assert.deepEqual(store.getState().selectedItemIdByActor, {
    pc_001: "torch",
    pc_002: "potion",
  });

  const switchToSecond = await store.selectActiveActor(
    "pc_002",
    "camp_001",
    "http://127.0.0.1:8000"
  );
  assert.equal(switchToSecond.ok, true);
  assert.equal(store.getState().campaign.active_actor_id, "pc_002");
  assert.equal(
    store.getState().selectedItemIdByActor[store.getState().campaign.active_actor_id],
    "potion"
  );

  const switchBack = await store.selectActiveActor(
    "pc_001",
    "camp_001",
    "http://127.0.0.1:8000"
  );
  assert.equal(switchBack.ok, true);
  assert.equal(store.getState().campaign.active_actor_id, "pc_001");
  assert.equal(
    store.getState().selectedItemIdByActor[store.getState().campaign.active_actor_id],
    "torch"
  );
});

test("recordTurnResult clears selected item when inventory snapshot removes it", async () => {
  const store = await loadStoreModule();
  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  store.setCampaignId("camp_001");

  store.recordTurnResult({
    effective_actor_id: "pc_001",
    state_summary: {
      active_actor_id: "pc_001",
      inventories: {
        pc_001: { torch: 1, rope: 1 },
      },
    },
  });
  assert.equal(store.setSelectedItemForActor("pc_001", "torch"), true);
  assert.equal(store.getState().selectedItemIdByActor.pc_001, "torch");

  store.recordTurnResult({
    effective_actor_id: "pc_001",
    state_summary: {
      active_actor_id: "pc_001",
      inventories: {
        pc_001: { rope: 1 },
      },
    },
  });

  assert.deepEqual(store.getState().inventoryByActor, {
    pc_001: { rope: 1 },
  });
  assert.equal(store.getState().selectedItemIdByActor.pc_001, null);
});

test("recordTurnResult clears selected item when inventory becomes empty", async () => {
  const store = await loadStoreModule();
  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  store.setCampaignId("camp_001");

  store.recordTurnResult({
    effective_actor_id: "pc_001",
    state_summary: {
      active_actor_id: "pc_001",
      inventories: {
        pc_001: { torch: 1 },
      },
    },
  });
  assert.equal(store.setSelectedItemForActor("pc_001", "torch"), true);

  store.recordTurnResult({
    effective_actor_id: "pc_001",
    state_summary: {
      active_actor_id: "pc_001",
      inventories: {
        pc_001: {},
      },
    },
  });

  assert.deepEqual(store.getState().inventoryByActor, {
    pc_001: {},
  });
  assert.equal(store.getState().selectedItemIdByActor.pc_001, null);
});

test("checkBackendReady stores not-ready reason and prompt message", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/runtime\/status$/);
    return jsonResponse({
      ready: false,
      reason: "passphrase_required",
    });
  };

  const result = await store.checkBackendReady("http://127.0.0.1:8000");

  assert.equal(result.ready, false);
  assert.equal(store.getState().backend.ready, false);
  assert.equal(store.getState().backend.reason, "passphrase_required");
  assert.match(
    store.getState().statusMessage,
    /unlock_keyring/i
  );
});

test("checkBackendReady stores ready state without breaking current flow", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/runtime\/status$/);
    return jsonResponse({
      ready: true,
      reason: "ready",
    });
  };

  const result = await store.checkBackendReady("http://127.0.0.1:8000");

  assert.equal(result.ready, true);
  assert.equal(store.getState().backend.ready, true);
  assert.equal(store.getState().backend.reason, "ready");
});

test("recoverFrontendSession stays non-fatal while backend is not ready", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/runtime\/status$/);
    return jsonResponse({
      ready: false,
      reason: "passphrase_required",
    });
  };

  const result = await store.recoverFrontendSession("http://127.0.0.1:8000");

  assert.equal(result.ok, false);
  assert.equal(result.recovered, false);
  assert.equal(store.getState().backend.ready, false);
  assert.deepEqual(store.getState().campaignOptions, []);
});

test("recoverFrontendSession reloads campaigns and active actor after backend becomes ready", async () => {
  const store = await loadStoreModule();
  const calls = [];
  global.fetch = async (url) => {
    calls.push(String(url));
    if (String(url).endsWith("/api/v1/runtime/status")) {
      return jsonResponse({
        ready: true,
        reason: "ready",
      });
    }
    if (String(url).endsWith("/api/v1/campaign/list")) {
      return jsonResponse({
        campaigns: [{ id: "camp_001", active_actor_id: "pc_002" }],
      });
    }
    if (String(url).includes("/api/v1/campaign/get?")) {
      return jsonResponse({
        campaign_id: "camp_001",
        selected: {
          party_character_ids: ["pc_001", "pc_002"],
          active_actor_id: "pc_002",
        },
        actors: ["pc_001", "pc_002"],
      });
    }
    throw new Error(`unexpected fetch: ${String(url)}`);
  };

  const result = await store.recoverFrontendSession("http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.equal(result.recovered, true);
  assert.equal(store.getState().campaignId, "camp_001");
  assert.equal(store.getState().campaign.active_actor_id, "pc_002");
  assert.deepEqual(store.getState().campaign.party_character_ids, ["pc_001", "pc_002"]);
  assert.equal(calls.length, 3);
});

test("refreshCampaignWorldPreview stores read-only world snapshot for the active campaign", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/campaigns\/camp_001\/world$/);
    return jsonResponse({
      world_id: "world_alpha",
      name: "World Alpha",
      world_description: "A frontier under tension.",
      objective: "Reach the signal tower.",
      start_area: "area_start",
    });
  };

  store.setCampaignId("camp_001");
  const result = await store.refreshCampaignWorldPreview("camp_001", "http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.deepEqual(store.getState().campaign.world, {
    world_id: "world_alpha",
    name: "World Alpha",
    world_description: "A frontier under tension.",
    objective: "Reach the signal tower.",
    start_area: "area_start",
  });
});

test("refreshCampaignWorldPreview clears world snapshot when world lookup fails", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/campaigns\/camp_001\/world$/);
    return jsonResponse({ detail: "campaign has no world_id: camp_001" }, 409);
  };

  store.setCampaignId("camp_001");
  store.getState().campaign.world = {
    world_id: "world_old",
    name: "Old World",
    world_description: "Old",
    objective: "Old objective",
    start_area: "area_old",
  };

  const result = await store.refreshCampaignWorldPreview("camp_001", "http://127.0.0.1:8000");

  assert.equal(result.ok, false);
  assert.equal(result.status, 409);
  assert.equal(store.getState().campaign.world, null);
});

test("silent readiness polling does not emit repeatedly when backend state is unchanged", async () => {
  const store = await loadStoreModule();
  let emits = 0;
  store.subscribe(() => {
    emits += 1;
  });
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/runtime\/status$/);
    return jsonResponse({
      ready: false,
      reason: "passphrase_required",
    });
  };

  await store.checkBackendReady("http://127.0.0.1:8000", { silent: true });
  const afterFirst = emits;
  await store.checkBackendReady("http://127.0.0.1:8000", { silent: true });

  assert.equal(afterFirst, 1);
  assert.equal(emits, 1);
});

test("createCampaignWithSelectedParty creates with optional world_id, loads selected characters, then sets active actor", async () => {
  const store = await loadStoreModule();
  const calls = [];
  let campaignGetCalls = 0;

  global.fetch = async (url, options = {}) => {
    const requestUrl = String(url);
    calls.push({
      url: requestUrl,
      method: options.method || "GET",
      body: options.body ? JSON.parse(String(options.body)) : null,
    });
    if (requestUrl.endsWith("/api/v1/campaign/create")) {
      assert.deepEqual(JSON.parse(String(options.body)), {
        party_character_ids: ["pc_002", "pc_003"],
        world_id: "world_existing_002",
      });
      return jsonResponse({ campaign_id: "camp_new" });
    }
    if (requestUrl.endsWith("/api/v1/campaign/list")) {
      return jsonResponse({
        campaigns: [{ id: "camp_new", active_actor_id: "pc_002" }],
      });
    }
    if (requestUrl.endsWith("/api/v1/campaigns/camp_new/party/load")) {
      const body = JSON.parse(String(options.body));
      return jsonResponse({
        ok: true,
        campaign_id: "camp_new",
        character_id: body.character_id,
        party_character_ids: ["pc_002", "pc_003"],
        active_actor_id: "pc_002",
      });
    }
    if (requestUrl.endsWith("/api/v1/campaign/select_actor")) {
      const body = JSON.parse(String(options.body));
      assert.equal(body.campaign_id, "camp_new");
      assert.equal(body.active_actor_id, "pc_003");
      return jsonResponse({ active_actor_id: "pc_003" });
    }
    if (requestUrl.includes("/api/v1/campaign/get?")) {
      campaignGetCalls += 1;
      const activeActorId = campaignGetCalls >= 3 ? "pc_003" : "pc_002";
      return jsonResponse({
        campaign_id: "camp_new",
        selected: {
          party_character_ids: ["pc_002", "pc_003"],
          active_actor_id: activeActorId,
        },
        actors: ["pc_002", "pc_003"],
        status: {
          ended: false,
          reason: null,
          ended_at: null,
          milestone: {
            current: "intro",
            last_advanced_turn: 0,
            turn_trigger_interval: 6,
            pressure: 0,
            pressure_threshold: 2,
            summary: "",
          },
        },
      });
    }
    throw new Error(`unexpected fetch: ${requestUrl}`);
  };

  const result = await store.createCampaignWithSelectedParty(
    {
      characterIds: ["pc_002", "pc_003"],
      activeActorId: "pc_003",
      worldId: "world_existing_002",
    },
    "http://127.0.0.1:8000"
  );

  assert.equal(result.ok, true);
  assert.equal(store.getState().campaignId, "camp_new");
  assert.deepEqual(store.getState().campaign.party_character_ids, ["pc_002", "pc_003"]);
  assert.equal(store.getState().campaign.active_actor_id, "pc_003");
  assert.equal(store.getState().character.selected_character_id, "pc_003");
  assert.equal(store.getState().campaignOptions[0].id, "camp_new");
  assert.equal(store.getState().campaignOptions[0].active_actor_id, "pc_003");
  assert.match(store.getState().statusMessage, /Created campaign camp_new with 2 selected character/);

  const loadCalls = calls.filter((entry) =>
    entry.url.endsWith("/api/v1/campaigns/camp_new/party/load")
  );
  assert.deepEqual(
    loadCalls.map((entry) => entry.body.character_id),
    ["pc_002", "pc_003"]
  );
});

test("createCampaignWithSelectedParty rejects empty explicit selection", async () => {
  const store = await loadStoreModule();

  const result = await store.createCampaignWithSelectedParty(
    { characterIds: [] },
    "http://127.0.0.1:8000"
  );

  assert.equal(result.ok, false);
  assert.equal(result.status, 400);
  assert.match(store.getState().statusMessage, /Select at least one character/i);
});

test("refreshWorlds stores authoritative world list from backend", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/worlds\/list$/);
    return jsonResponse([
      {
        world_id: "world_beta",
        name: "World Beta",
        generator: { id: "stub" },
        updated_at: "2026-03-10T00:00:00Z",
      },
    ]);
  };

  const result = await store.refreshWorlds("http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.equal(store.getState().worlds.status, "idle");
  assert.equal(store.getState().worlds.error, null);
  assert.deepEqual(store.getState().worlds.list, [
    {
      world_id: "world_beta",
      name: "World Beta",
      generator: { id: "stub" },
      updated_at: "2026-03-10T00:00:00Z",
    },
  ]);
});

test("generateWorldResource posts minimal payload then refreshes world list", async () => {
  const store = await loadStoreModule();
  const calls = [];
  global.fetch = async (url, options = {}) => {
    const requestUrl = String(url);
    calls.push({
      url: requestUrl,
      method: options.method || "GET",
      body: options.body ? JSON.parse(String(options.body)) : null,
    });
    if (requestUrl.endsWith("/api/v1/worlds/generate")) {
      assert.deepEqual(JSON.parse(String(options.body)), {
        world_id: "world_new_ui",
        name: "World From UI",
      });
      return jsonResponse({
        world_id: "world_new_ui",
        name: "World From UI",
        generator: { id: "stub" },
        updated_at: "2026-03-10T00:00:00Z",
        created: true,
        normalized: true,
      });
    }
    if (requestUrl.endsWith("/api/v1/worlds/list")) {
      return jsonResponse([
        {
          world_id: "world_new_ui",
          name: "World From UI",
          generator: { id: "stub" },
          updated_at: "2026-03-10T00:00:00Z",
        },
      ]);
    }
    throw new Error(`unexpected fetch: ${requestUrl}`);
  };

  store.setWorldGenerateForm({
    world_id: "world_new_ui",
    name: "World From UI",
  });
  const result = await store.generateWorldResource("http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.equal(store.getState().worlds.status, "idle");
  assert.equal(store.getState().worlds.error, null);
  assert.equal(store.getState().worlds.last_generated_world_id, "world_new_ui");
  assert.equal(store.getState().worlds.generate_form.world_id, "");
  assert.equal(store.getState().worlds.generate_form.name, "World From UI");
  assert.deepEqual(store.getState().worlds.list, [
    {
      world_id: "world_new_ui",
      name: "World From UI",
      generator: { id: "stub" },
      updated_at: "2026-03-10T00:00:00Z",
    },
  ]);
  assert.deepEqual(
    calls.map((entry) => `${entry.method} ${entry.url.split("/api/v1/")[1]}`),
    ["POST worlds/generate", "GET worlds/list"]
  );
});
