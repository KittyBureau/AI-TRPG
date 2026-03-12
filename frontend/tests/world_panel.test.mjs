import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadWorldPanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/world_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("formatWorldSummary labels scenario-backed worlds lightly", async () => {
  const { formatWorldSummary } = await loadWorldPanelModule();

  assert.equal(
    formatWorldSummary({
      world_id: "world_scenario_ui",
      name: "Scenario From UI",
      generator: { id: "playable_scenario_v0" },
      scenario: {
        label: "Key Gate Scenario",
        template_id: "key_gate_scenario",
        area_count: 6,
        difficulty: "standard",
      },
      updated_at: "2026-03-10T00:00:00Z",
    }),
    "Scenario From UI (world_scenario_ui) | scenario-backed | Key Gate Scenario | 6 areas | standard | updated=2026-03-10T00:00:00Z"
  );
});

test("formatWorldSummary keeps generator label for non-scenario worlds", async () => {
  const { formatWorldSummary } = await loadWorldPanelModule();

  assert.equal(
    formatWorldSummary({
      world_id: "world_stub_ui",
      name: "Stub From UI",
      generator: { id: "stub" },
      updated_at: "2026-03-10T00:00:00Z",
    }),
    "Stub From UI (world_stub_ui) | generator=stub | updated=2026-03-10T00:00:00Z"
  );
});
