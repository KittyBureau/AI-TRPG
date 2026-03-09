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
      selected: {
        party_character_ids: ["pc_001", "pc_002"],
        active_actor_id: "pc_002",
      },
    });
  };

  store.setCampaignOptions([{ id: "camp_001", active_actor_id: "pc_001" }]);
  const result = await store.refreshCampaign("camp_001", "http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.deepEqual(store.getState().campaign.party_character_ids, ["pc_001", "pc_002"]);
  assert.equal(store.getState().campaign.active_actor_id, "pc_002");
  assert.equal(store.getState().campaignOptions[0].active_actor_id, "pc_002");
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
        selected: {
          party_character_ids: ["pc_001", "pc_002"],
          active_actor_id: "pc_002",
        },
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
        selected: {
          party_character_ids: ["pc_001", "pc_002"],
          active_actor_id: activeActorId,
        },
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
        selected: {
          party_character_ids: ["pc_001", "pc_002"],
          active_actor_id: "pc_002",
        },
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
