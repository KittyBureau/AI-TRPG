import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadPanelModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/panels/actor_control_panel.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("buildSceneActionPrompt encodes selected-target scene actions explicitly", async () => {
  const { buildSceneActionPrompt } = await loadPanelModule();
  const prompt = buildSceneActionPrompt("pc_001", "talk", "guide_01");

  assert.match(prompt, /scene_action/);
  assert.match(prompt, /"action":"talk"/);
  assert.match(prompt, /"target_id":"guide_01"/);
});

test("buildTurnPayload includes selected_stack_id on the primary path", async () => {
  const { buildTurnPayload } = await loadPanelModule();
  const payload = buildTurnPayload(
    {
      campaignId: "camp_001",
    },
    "pc_001",
    "use the torch",
    {
      buildTurnContextHintsForActor() {
        return {
          selected_stack_id: "stk_torch_0001",
        };
      },
    }
  );

  assert.deepEqual(payload, {
    campaign_id: "camp_001",
    user_input: "use the torch",
    execution: { actor_id: "pc_001" },
    context_hints: {
      selected_stack_id: "stk_torch_0001",
    },
  });
});

test("buildTurnPayload keeps explicit fallback-only hints when that is the selected path", async () => {
  const { buildTurnPayload } = await loadPanelModule();
  const payload = buildTurnPayload(
    {
      campaignId: "camp_001",
    },
    "pc_001",
    "use the torch",
    {
      buildTurnContextHintsForActor() {
        return {
          selected_item_id: "torch",
        };
      },
    }
  );

  assert.deepEqual(payload, {
    campaign_id: "camp_001",
    user_input: "use the torch",
    execution: { actor_id: "pc_001" },
    context_hints: {
      selected_item_id: "torch",
    },
  });
});

test("buildTurnPayload forwards selected_target_id alongside other hints", async () => {
  const { buildTurnPayload } = await loadPanelModule();
  const payload = buildTurnPayload(
    {
      campaignId: "camp_001",
    },
    "pc_001",
    "take the selected item",
    {
      buildTurnContextHintsForActor() {
        return {
          selected_stack_id: "stk_torch_0001",
          selected_target_id: "apple_01",
        };
      },
    }
  );

  assert.deepEqual(payload, {
    campaign_id: "camp_001",
    user_input: "take the selected item",
    execution: { actor_id: "pc_001" },
    context_hints: {
      selected_stack_id: "stk_torch_0001",
      selected_target_id: "apple_01",
    },
  });
});
