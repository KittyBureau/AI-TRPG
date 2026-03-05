# Storage Authority (Runtime)

## Implemented

### Actor state authority

Authoritative runtime state is stored at:

- `campaign.json.actors[actor_id].position`
- `campaign.json.actors[actor_id].hp`
- `campaign.json.actors[actor_id].character_state`
- `campaign.json.actors[actor_id].inventory`

### Legacy mirrors

Legacy fields remain for compatibility only:

- `campaign.json.positions`
- `campaign.json.hp`
- `campaign.json.character_states`
- `campaign.json.state.positions*`

Current persistence path (`FileRepo.save_campaign`) clears these mirror maps on save.

### Migration behavior

When loading old campaign payloads without `actors`, runtime migrates legacy maps into `actors` and then clears mirrors.

## Planned / Non-goals for Playable v1

- No new persistence schema split for actor runtime state in Playable v1.
- No removal of legacy mirrors yet; keep compatibility behavior stable.

## Related Specs and Code

- Spec: `docs/01_specs/storage_layout.md`
- Spec: `docs/01_specs/state_machine.md`
- Code: `backend/infra/file_repo.py`
- Code: `backend/domain/character_access.py`
- Code: `backend/domain/models.py`
