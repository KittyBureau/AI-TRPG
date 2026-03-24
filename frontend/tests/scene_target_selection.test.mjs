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

test("refreshMapView stores current area scene entities and reachable areas", async () => {
  const store = await loadStoreModule();
  global.fetch = async (url) => {
    assert.match(String(url), /\/api\/v1\/map\/view\?/);
    return jsonResponse({
      campaign_id: "camp_001",
      active_actor_id: "pc_001",
      current_area: {
        id: "area_001",
        name: "Start",
      },
      current_area_actor_ids: ["pc_001"],
      reachable_areas: [
        {
          id: "area_002",
          name: "Hall",
        },
      ],
      entities_in_area: [
        {
          id: "npc_01",
          kind: "npc",
          label: "Porter",
          tags: ["npc"],
          verbs: ["inspect", "talk"],
          state: {},
        },
        {
          id: "apple_01",
          kind: "item",
          label: "Apple",
          tags: ["loot"],
          verbs: ["inspect", "take"],
          state: {},
        },
      ],
    });
  };

  const result = await store.refreshMapView("camp_001", "pc_001", "http://127.0.0.1:8000");

  assert.equal(result.ok, true);
  assert.deepEqual(store.getState().mapView, {
    campaign_id: "camp_001",
    active_actor_id: "pc_001",
    current_area: { id: "area_001", name: "Start" },
    current_area_actor_ids: ["pc_001"],
    reachable_areas: [{ id: "area_002", name: "Hall" }],
    entities_in_area: [
      {
        id: "npc_01",
        kind: "npc",
        label: "Porter",
        tags: ["npc"],
        verbs: ["inspect", "talk"],
        state: {},
      },
      {
        id: "apple_01",
        kind: "item",
        label: "Apple",
        tags: ["loot"],
        verbs: ["inspect", "take"],
        state: {},
      },
    ],
  });
});

test("selected scene target is stored per active actor and emitted through turn context hints", async () => {
  const store = await loadStoreModule();
  store.getState().campaign.active_actor_id = "pc_001";
  store.getState().mapView = {
    campaign_id: "camp_001",
    active_actor_id: "pc_001",
    current_area: { id: "area_001", name: "Start" },
    current_area_actor_ids: ["pc_001"],
    reachable_areas: [],
    entities_in_area: [
      {
        id: "apple_01",
        kind: "item",
        label: "Apple",
        tags: ["loot"],
        verbs: ["inspect", "take"],
        state: {},
      },
      {
        id: "crate_01",
        kind: "container",
        label: "Crate",
        tags: ["container"],
        verbs: ["inspect", "open", "search"],
        state: {},
      },
    ],
  };

  assert.equal(store.setSelectedSceneTargetForActor("pc_001", "apple_01"), true);
  assert.equal(store.setSelectedSceneTargetForActor("pc_001", "crate_01"), false);
  assert.deepEqual(store.getSelectedSceneTargetForActor("pc_001"), {
    id: "apple_01",
    kind: "item",
    label: "Apple",
    tags: ["loot"],
    verbs: ["inspect", "take"],
    state: {},
  });
  assert.deepEqual(store.buildTurnContextHintsForActor("pc_001"), {
    selected_target_id: "apple_01",
  });
});
