import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadWorldPreviewPanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/world_preview_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("deriveWorldPreviewView returns world preview fields when world data exists", async () => {
  const { deriveWorldPreviewView } = await loadWorldPreviewPanelModule();

  const view = deriveWorldPreviewView({
    campaignId: "camp_001",
    campaign: {
      world: {
        world_id: "world_alpha",
        name: "World Alpha",
        world_description: "A frontier under tension.",
        objective: "Reach the signal tower.",
        start_area: "area_start",
      },
    },
  });

  assert.equal(view.campaignId, "camp_001");
  assert.equal(view.hasWorld, true);
  assert.deepEqual(view.world, {
    world_id: "world_alpha",
    name: "World Alpha",
    world_description: "A frontier under tension.",
    objective: "Reach the signal tower.",
    start_area: "area_start",
  });
});

test("deriveWorldPreviewView handles missing world data gracefully", async () => {
  const { deriveWorldPreviewView } = await loadWorldPreviewPanelModule();

  const view = deriveWorldPreviewView({
    campaignId: "camp_001",
    campaign: {
      world: null,
    },
  });

  assert.equal(view.campaignId, "camp_001");
  assert.equal(view.hasWorld, false);
  assert.equal(view.world, null);
});
