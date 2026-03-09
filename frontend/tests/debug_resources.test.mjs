import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { pathToFileURL } from "node:url";

async function loadDebugResourcesModule() {
  const modulePath = pathToFileURL(
    path.resolve("frontend/utils/debug_resources.js")
  ).href;
  return import(`${modulePath}?t=${Date.now()}_${Math.random()}`);
}

test("extractDebugResourcesFromResponseText prefers debug.resources including policies", async () => {
  const { extractDebugResourcesFromResponseText } = await loadDebugResourcesModule();

  const view = extractDebugResourcesFromResponseText(
    JSON.stringify({
      debug: {
        resources: {
          prompts: [],
          flows: [],
          schemas: [],
          templates: [],
          template_usage: [],
          policies: [{ name: "policy_a" }],
        },
      },
    })
  );

  assert.equal(view.available, true);
  assert.equal(view.source, "resources");
  assert.equal(view.resources.policies.length, 1);
  assert.equal(view.resources.policies[0].name, "policy_a");
});

test("buildDebugResourcesView keeps policies category empty in legacy fallback", async () => {
  const { buildDebugResourcesView } = await loadDebugResourcesModule();

  const view = buildDebugResourcesView({
    used_prompt_name: "p",
    used_flow_name: "f",
  });

  assert.equal(view.available, true);
  assert.equal(view.source, "legacy");
  assert.ok(Array.isArray(view.resources.policies));
  assert.equal(view.resources.policies.length, 0);
});

test("buildDebugResourcesView tolerates malformed policies payload", async () => {
  const { buildDebugResourcesView } = await loadDebugResourcesModule();

  const view = buildDebugResourcesView({
    resources: {
      prompts: [],
      flows: [],
      schemas: [],
      templates: [],
      template_usage: [],
      policies: { name: "not-an-array" },
    },
  });

  assert.equal(view.available, true);
  assert.equal(view.source, "resources");
  assert.ok(Array.isArray(view.resources.policies));
  assert.equal(view.resources.policies.length, 0);
});
