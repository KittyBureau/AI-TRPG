export const RESOURCE_CATEGORIES = [
  "prompts",
  "flows",
  "schemas",
  "templates",
  "template_usage",
];

function emptyResources() {
  return {
    prompts: [],
    flows: [],
    schemas: [],
    templates: [],
    template_usage: [],
  };
}

function toList(value) {
  if (Array.isArray(value)) {
    return value.filter((item) => item && typeof item === "object");
  }
  if (value && typeof value === "object") {
    return [value];
  }
  return [];
}

function toStringValue(value) {
  return typeof value === "string" ? value : "";
}

function toBoolValue(value) {
  return value === true;
}

function normalizePromptEntry(entry) {
  const sourceHash =
    toStringValue(entry.source_hash) ||
    toStringValue(entry.hash) ||
    toStringValue(entry.used_prompt_hash);
  const renderedHash = toStringValue(entry.rendered_hash);
  return {
    name: toStringValue(entry.name),
    version: toStringValue(entry.version),
    source_hash: sourceHash,
    rendered_hash: renderedHash,
    hash: sourceHash,
    fallback: toBoolValue(entry.fallback),
  };
}

function normalizeSimpleEntry(entry) {
  return {
    name: toStringValue(entry.name),
    version: toStringValue(entry.version),
    hash: toStringValue(entry.hash) || toStringValue(entry.source_hash),
    fallback: toBoolValue(entry.fallback),
  };
}

function normalizeTemplateUsageEntry(entry) {
  return {
    name: toStringValue(entry.name),
    version: toStringValue(entry.version),
    hash: toStringValue(entry.hash),
    fallback: toBoolValue(entry.fallback),
    applied: typeof entry.applied === "boolean" ? entry.applied : null,
  };
}

function normalizeResources(resources) {
  return {
    prompts: toList(resources.prompts).map(normalizePromptEntry),
    flows: toList(resources.flows).map(normalizeSimpleEntry),
    schemas: toList(resources.schemas).map(normalizeSimpleEntry),
    templates: toList(resources.templates).map(normalizeSimpleEntry),
    template_usage: toList(resources.template_usage).map(normalizeTemplateUsageEntry),
  };
}

function buildLegacyResources(debug) {
  const promptEntry =
    debug.prompt && typeof debug.prompt === "object"
      ? debug.prompt
      : {
          name: debug.used_prompt_name,
          version: debug.used_prompt_version,
          source_hash: debug.used_prompt_source_hash || debug.used_prompt_hash,
          rendered_hash: debug.used_prompt_rendered_hash,
          fallback: debug.used_prompt_fallback === true,
        };
  const flowEntry =
    debug.flow && typeof debug.flow === "object"
      ? debug.flow
      : {
          name: debug.used_flow_name,
          version: debug.used_flow_version,
          hash: debug.used_flow_hash,
          fallback: debug.used_flow_fallback === true,
        };

  return normalizeResources({
    prompts: promptEntry && (promptEntry.name || promptEntry.version) ? [promptEntry] : [],
    flows: flowEntry && (flowEntry.name || flowEntry.version) ? [flowEntry] : [],
    schemas: debug.schemas,
    templates: debug.templates,
    template_usage: debug.template_usage,
  });
}

export function buildDebugResourcesView(debug) {
  if (!debug || typeof debug !== "object") {
    return {
      available: false,
      source: "none",
      resources: emptyResources(),
    };
  }
  if (debug.resources && typeof debug.resources === "object") {
    return {
      available: true,
      source: "resources",
      resources: normalizeResources(debug.resources),
    };
  }
  return {
    available: true,
    source: "legacy",
    resources: buildLegacyResources(debug),
  };
}

export function extractDebugResourcesFromResponseText(responseText) {
  if (typeof responseText !== "string" || !responseText.trim()) {
    return {
      available: false,
      source: "none",
      reason: "trace disabled / no debug",
      resources: emptyResources(),
    };
  }
  let payload = null;
  try {
    payload = JSON.parse(responseText);
  } catch (_error) {
    return {
      available: false,
      source: "none",
      reason: "trace disabled / no debug",
      resources: emptyResources(),
    };
  }
  if (!payload || typeof payload !== "object") {
    return {
      available: false,
      source: "none",
      reason: "trace disabled / no debug",
      resources: emptyResources(),
    };
  }
  if (!payload.debug || typeof payload.debug !== "object") {
    return {
      available: false,
      source: "none",
      reason: "trace disabled / no debug",
      resources: emptyResources(),
    };
  }
  const view = buildDebugResourcesView(payload.debug);
  return {
    available: view.available,
    source: view.source,
    reason: "",
    resources: view.resources,
  };
}

export function formatResourceEntry(category, entry) {
  const fallback = entry?.fallback === true ? "true" : "false";
  const name = toStringValue(entry?.name) || "(unnamed)";
  const version = toStringValue(entry?.version) || "(unknown)";
  if (category === "prompts") {
    const sourceHash = toStringValue(entry?.source_hash) || "-";
    const renderedHash = toStringValue(entry?.rendered_hash) || "-";
    return `${name} @ ${version} | source_hash=${sourceHash} | rendered_hash=${renderedHash} | fallback=${fallback}`;
  }
  if (category === "template_usage") {
    const hash = toStringValue(entry?.hash) || "-";
    const applied =
      typeof entry?.applied === "boolean" ? String(entry.applied) : "unknown";
    return `${name} @ ${version} | hash=${hash} | fallback=${fallback} | applied=${applied}`;
  }
  const hash = toStringValue(entry?.hash) || "-";
  return `${name} @ ${version} | hash=${hash} | fallback=${fallback}`;
}
