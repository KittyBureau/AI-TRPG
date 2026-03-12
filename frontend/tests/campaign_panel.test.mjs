import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadPanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/campaign_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("formatCampaignStatusLines renders authoritative status and milestone lines", async () => {
  const { formatCampaignStatusLines } = await loadPanelModule();

  assert.deepEqual(
    formatCampaignStatusLines({
      ended: false,
      reason: null,
      ended_at: null,
      milestone: {
        current: "intro",
        summary: "opened with the first checkpoint",
      },
    }),
    [
      "Status: active",
      "Milestone: intro",
      "Milestone summary: opened with the first checkpoint",
    ]
  );
});

test("formatCampaignStatusLines falls back cleanly when status snapshot is unavailable", async () => {
  const { formatCampaignStatusLines } = await loadPanelModule();

  assert.deepEqual(formatCampaignStatusLines(null), [
    "Campaign status unavailable until authoritative refresh succeeds.",
  ]);
});

test("formatWorldOptionLabel highlights scenario-backed worlds with lightweight detail", async () => {
  const { formatWorldOptionLabel } = await loadPanelModule();

  assert.equal(
    formatWorldOptionLabel({
      world_id: "world_scenario_ui",
      name: "Scenario From UI",
      generator: { id: "playable_scenario_v0" },
      scenario: {
        label: "Key Gate Scenario",
        template_id: "key_gate_scenario",
        area_count: 6,
        difficulty: "easy",
      },
    }),
    "Scenario From UI (world_scenario_ui) - scenario-backed | Key Gate Scenario | 6 areas | easy"
  );
});

test("formatWorldOptionLabel keeps non-scenario world labels compact", async () => {
  const { formatWorldOptionLabel } = await loadPanelModule();

  assert.equal(
    formatWorldOptionLabel({
      world_id: "world_stub_ui",
      name: "Stub From UI",
      generator: { id: "stub" },
    }),
    "Stub From UI (world_stub_ui, stub)"
  );
});
