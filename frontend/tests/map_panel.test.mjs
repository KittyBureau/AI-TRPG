import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadMapPanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/map_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("deriveMapPanelView uses campaign snapshot as truth and applies matching state_summary labels", async () => {
  const { deriveMapPanelView } = await loadMapPanelModule();

  const view = deriveMapPanelView({
    campaign: {
      party_character_ids: ["pc_001"],
      active_actor_id: "pc_001",
      actors: {
        pc_001: {
          position: "area_001",
        },
      },
      map: {
        areas: {
          area_001: {
            id: "area_001",
            name: "Camp",
            description: "Base description",
            reachable_area_ids: ["area_002"],
          },
          area_002: {
            id: "area_002",
            name: "Gate",
            description: "North gate",
            reachable_area_ids: [],
          },
        },
      },
    },
    stateSummary: {
      active_actor_id: "pc_001",
      active_area_id: "area_001",
      active_area_name: "Campfire",
      active_area_description: "Summary override",
    },
  });

  assert.equal(view.activeActorId, "pc_001");
  assert.equal(view.currentArea.id, "area_001");
  assert.equal(view.currentArea.name, "Campfire");
  assert.equal(view.currentArea.description, "Summary override");
  assert.deepEqual(view.reachableAreas, [
    {
      id: "area_002",
      name: "Gate",
      description: "North gate",
    },
  ]);
});

test("deriveMapPanelView ignores mismatched state_summary area labels", async () => {
  const { deriveMapPanelView } = await loadMapPanelModule();

  const view = deriveMapPanelView({
    campaign: {
      party_character_ids: ["pc_001"],
      active_actor_id: "pc_001",
      actors: {
        pc_001: {
          position: "area_001",
        },
      },
      map: {
        areas: {
          area_001: {
            id: "area_001",
            name: "Camp",
            description: "Base description",
            reachable_area_ids: [],
          },
        },
      },
    },
    stateSummary: {
      active_actor_id: "pc_001",
      active_area_id: "area_999",
      active_area_name: "Wrong area",
      active_area_description: "Should not be used",
    },
  });

  assert.equal(view.currentArea.name, "Camp");
  assert.equal(view.currentArea.description, "Base description");
});
