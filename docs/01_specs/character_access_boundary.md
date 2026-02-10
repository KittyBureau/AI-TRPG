# Character Access Boundary

Purpose: centralize character state access behind one thin boundary so storage
can be swapped later without rewriting turn logic.

## Fact vs State

- `CharacterFact`: descriptive, mostly static profile fields.
- `CharacterState`: runtime mutable fields (`position`, `hp`, `character_state`).
- `CharacterView`: merged output for read models. Runtime state values remain
  authoritative for mutable fields.

Current implementation is in:

- `backend/domain/character_access.py`
  - `CharacterState`, `CharacterFact`, `CharacterView`
  - `CampaignCharacterStateStore`
  - `StubCharacterFactStore`
  - `CharacterFacade`
- Runtime file-backed CharacterFact read implementation:
  - `backend/infra/character_fact_store.py` (`GeneratedCharacterFactStore`)
  - `backend/app/character_facade_factory.py` (`create_runtime_character_facade`)

## Current Source Of Truth

- Campaign persistence stays at `storage/campaigns/<campaign_id>/campaign.json`.
- Runtime authoritative actor state remains `campaign.actors`.
- Legacy compatibility maps (`positions`, `hp`, `character_states`) are kept as
  mirrors for compatibility paths and prompt/state-summary payload assembly.
- No API contract changes are introduced by this boundary.

## Usage Rule

- Do not access `campaign.positions`, `campaign.hp`, or
  `campaign.character_states` directly in turn/tool critical paths.
- Use `CharacterFacade`:
  - `get_state(campaign, character_id)`
  - `set_state(campaign, character_id, state)`
  - `get_view(campaign, character_id)`
  - `list_party_views(campaign)`
  - `build_state_maps(campaign, character_ids=None)`
- Runtime creation should prefer `create_runtime_character_facade` so fact reads
  can include generated draft files with soft-fail fallback.

## Planned Storage Migration (Not Implemented Yet)

`StubCharacterFactStore` intentionally keeps TODO hooks for:

- `storage/characters_library/{id}.json`
- `storage/campaigns/{campaign_id}/characters/{id}.fact.json`

Future per-campaign mutable state target:

- `storage/campaigns/{campaign_id}/characters/{id}.state.json`

When those adapters are added, application code should continue using
`CharacterFacade` unchanged.
