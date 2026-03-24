function normalizeString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : "";
}

function normalizedSceneVerbList(entity) {
  return Array.isArray(entity?.verbs)
    ? entity.verbs
        .filter((verb) => typeof verb === "string" && verb.trim())
        .map((verb) => verb.trim().toLowerCase())
    : [];
}

function sceneEntitySupportsAction(entity, action) {
  const normalizedAction = normalizeString(action).toLowerCase();
  const verbs = normalizedSceneVerbList(entity);
  if (normalizedAction === "talk") {
    return normalizeString(entity?.kind).toLowerCase() === "npc" || verbs.includes("talk");
  }
  return verbs.includes(normalizedAction);
}

function deriveSceneEntityFlags(entity) {
  const verbs = normalizedSceneVerbList(entity);
  const talkable = sceneEntitySupportsAction(entity, "talk");
  const inspectable = sceneEntitySupportsAction(entity, "inspect");
  const usable = sceneEntitySupportsAction(entity, "use");
  const takeable = sceneEntitySupportsAction(entity, "take");
  const interactable = talkable || inspectable || usable || verbs.includes("open") || verbs.includes("search");
  const selectable = talkable || inspectable || usable || takeable;
  return {
    visible: Boolean(entity && typeof entity === "object"),
    interactable,
    selectable,
    talkable,
    inspectable,
    usable,
    takeable,
    searchable: verbs.includes("search"),
    openable: verbs.includes("open"),
  };
}

function deriveSceneAffordanceTags(entity) {
  const flags = deriveSceneEntityFlags(entity);
  const tags = ["Visible"];
  if (flags.interactable) {
    tags.push("Interactable");
  }
  if (flags.takeable) {
    tags.push("Takeable");
    tags.push("Take");
  }
  if (flags.talkable) {
    tags.push("Talk");
  }
  if (flags.inspectable) {
    tags.push("Inspect");
  }
  if (flags.usable) {
    tags.push("Use");
  }
  if (flags.openable) {
    tags.push("Open");
  }
  if (flags.searchable) {
    tags.push("Search");
  }
  return [...new Set(tags)];
}

function selectedTargetActionLabels(entity) {
  const labels = [];
  if (sceneEntitySupportsAction(entity, "talk")) {
    labels.push("Talk");
  }
  if (sceneEntitySupportsAction(entity, "inspect")) {
    labels.push("Inspect");
  }
  if (sceneEntitySupportsAction(entity, "use")) {
    labels.push("Use");
  }
  if (sceneEntitySupportsAction(entity, "take")) {
    labels.push("Take");
  }
  return labels;
}

export {
  deriveSceneAffordanceTags,
  deriveSceneEntityFlags,
  normalizedSceneVerbList,
  sceneEntitySupportsAction,
  selectedTargetActionLabels,
};
