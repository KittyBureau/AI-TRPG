# Storage Authority (Runtime)

## Implemented

### Actor state authority

Authoritative runtime state is stored at:

- `campaign.json.actors[actor_id].position`
- `campaign.json.actors[actor_id].hp`
- `campaign.json.actors[actor_id].character_state`

### Portable item authority

Authoritative portable-item runtime state is stored at:

- `campaign.json.items[stack_id]`

Current runtime policy:

- `campaign.json.items` is the single authority for portable item stacks.
- `campaign.json.actors[actor_id].inventory` is a derived compatibility view only.
- inventory read paths should derive from `campaign.json.items`, not from stored actor inventory maps.
- inventory-only campaign payloads are no longer supported for item initialization.
- frontend inventory authority derives from stack payloads (`inventory_stacks`), with aggregated inventory retained only as a derived display/debug view.
- frontend selection authority is `selectedStackId`; `selected_item_id` is fallback-only compatibility.
- mainline portable-item acquisition is `search -> reveal -> take`; `search` alone does not grant actor possession.
- `inventory_add` remains a bounded legacy-only contract for source-entity-backed inventory gain.

### Legacy mirrors

Legacy fields remain for compatibility only:

- `campaign.json.positions`
- `campaign.json.hp`
- `campaign.json.character_states`
- `campaign.json.state.positions*`

Current persistence path (`FileRepo.save_campaign`) clears these mirror maps on save.

### Migration behavior

When loading old campaign payloads without `actors`, runtime migrates legacy maps into `actors` and then clears mirrors.

For items, there is no old-save migration path:

- repository fixtures/bootstrap now initialize `campaign.json.items` directly
- runtime syncs `actors[*].inventory` from `campaign.items`
- inventory-only payloads are treated as invalid for Phase 1 item authority

## Planned / Non-goals for Playable v1

- No new persistence schema split for actor runtime state in Playable v1.
- No removal of legacy mirrors yet; keep compatibility behavior stable.

## Related Specs and Code

- Spec: `docs/01_specs/storage_layout.md`
- Guide: `docs/20_runtime/item_runtime_model.md`
- Spec: `docs/01_specs/state_machine.md`
- Code: `backend/infra/file_repo.py`
- Code: `backend/domain/character_access.py`
- Code: `backend/domain/models.py`
