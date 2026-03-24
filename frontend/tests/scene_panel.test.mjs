import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadScenePanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/scene_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("deriveScenePanelView splits NPCs, interactives, and takeable items from mapView", async () => {
  const { deriveScenePanelView } = await loadScenePanelModule();

  const view = deriveScenePanelView({
    campaign: {
      active_actor_id: "pc_001",
      actors: {
        pc_001: { position: "area_001" },
      },
      map: {
        areas: {
          area_001: {
            id: "area_001",
            description: "Fallback description",
          },
        },
      },
    },
    stateSummary: {
      active_area_description: "Scene summary",
    },
    mapView: {
      active_actor_id: "pc_001",
      current_area: { id: "area_001", name: "Archive Lobby" },
      entities_in_area: [
        {
          id: "porter_npc",
          kind: "npc",
          label: "Night Porter",
          tags: ["npc"],
          verbs: ["inspect", "talk"],
          state: {},
        },
        {
          id: "notice_board",
          kind: "object",
          label: "Notice Board",
          tags: ["notice"],
          verbs: ["inspect"],
          state: {},
        },
        {
          id: "office_pass",
          kind: "item",
          label: "Office Pass",
          tags: ["pass"],
          verbs: ["inspect", "take"],
          state: { quantity: 1 },
        },
      ],
    },
  });

  assert.equal(view.activeActorId, "pc_001");
  assert.equal(view.currentAreaName, "Archive Lobby");
  assert.equal(view.currentAreaDescription, "Scene summary");
  assert.deepEqual(view.npcs.map((entity) => entity.id), ["porter_npc"]);
  assert.deepEqual(view.interactives.map((entity) => entity.id), ["notice_board"]);
  assert.deepEqual(view.takeables.map((entity) => entity.id), ["office_pass"]);
});
