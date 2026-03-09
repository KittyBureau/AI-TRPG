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
