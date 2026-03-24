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

test("deriveScenePanelView exposes visible, interactable, and takeable affordances from mapView", async () => {
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
  assert.equal(view.visibleCount, 3);
  assert.equal(view.interactableCount, 3);
  assert.equal(view.takeableCount, 1);
  assert.deepEqual(view.npcs.map((entity) => entity.id), ["porter_npc"]);
  assert.deepEqual(view.interactives.map((entity) => entity.id), ["notice_board"]);
  assert.deepEqual(view.takeables.map((entity) => entity.id), ["office_pass"]);
  assert.deepEqual(view.npcs[0].flags, {
    visible: true,
    interactable: true,
    selectable: true,
    talkable: true,
    inspectable: true,
    usable: false,
    takeable: false,
    searchable: false,
    openable: false,
  });
  assert.deepEqual(view.npcs[0].affordance_tags, ["Visible", "Interactable", "Talk", "Inspect"]);
  assert.deepEqual(view.interactives[0].affordance_tags, ["Visible", "Interactable", "Inspect"]);
  assert.deepEqual(view.takeables[0].affordance_tags, ["Visible", "Interactable", "Takeable", "Take", "Inspect"]);
});
