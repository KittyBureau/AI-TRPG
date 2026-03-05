export function getPartyActorIds(state) {
  const party = state?.campaign?.party_character_ids;
  if (!Array.isArray(party)) {
    return [];
  }
  return party
    .filter((value) => typeof value === "string" && value.trim())
    .map((value) => value.trim());
}

export function resolveActingActorId(state) {
  const party = getPartyActorIds(state);
  if (!party.length) {
    return "";
  }
  const activeActorId =
    typeof state?.campaign?.active_actor_id === "string"
      ? state.campaign.active_actor_id.trim()
      : "";
  if (activeActorId && party.includes(activeActorId)) {
    return activeActorId;
  }
  return party[0];
}
