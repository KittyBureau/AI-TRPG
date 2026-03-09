# Architecture Overview (Stage 1)

This backend is organized by layers to keep authority boundaries clear and enable
incremental delivery.

## Layers

- `backend/api/`: FastAPI transport only. Maps HTTP to application services.
- `backend/app/`: Turn orchestration. Coordinates dialog rules, LLMClient, and storage.
- `backend/domain/`: Pure domain rules (dialog type classifier, models).
- `backend/infra/`: File storage and FakeLLM implementation.
- `storage/`: Local persistence rooted at the workspace.

## Character Access Boundary

- Character access is centralized in `backend/domain/character_access.py`.
- Critical-path reads/writes for `position`, `hp`, and `character_state` should
  go through `CharacterFacade` rather than ad-hoc map access.
- This keeps turn/tool logic independent from future character storage adapter
  changes.
- Generated CharacterFact persistence uses app/infra split:
  - orchestration: `backend/app/character_fact_generation.py`
  - file IO: `backend/infra/file_repo.py` and `backend/infra/character_fact_store.py`

## Future Direction (Informational Only)

Prompt generation may move toward a **state-driven context model** where the
world state is summarized through tags and area states instead of replaying full
dialogue history. This is a future context-optimization direction only and does
not change current runtime behavior.

Current source of truth remains the existing turn payload assembly inside
`TurnService.submit_turn()` and `_build_system_prompt()`. A future context
system is not an implemented architecture module in Playable v1.

If a future context selection/preparation layer is added, it should attach
inside `TurnService.submit_turn()` after authoritative runtime inputs are
resolved and before `_build_system_prompt()` assembles the final prompt payload.
That layer must still feed the existing payload builder rather than creating a
second runtime path.

Any future context extension must not bypass:

- `campaign.actors`
- `campaign.entities`
- `selected`
- `map`
- `settings_snapshot`
- the current runtime authority chain already enforced by `turn_service.py`

Non-goals for P1-13:

- no context compression
- no context layering or memory split
- no tag/state memory system
- no area-scoped archive/store
- no new context manager or builder module
- no new storage persistence for context artifacts
- no prompt builder refactor

## Stage 1 Data Flow

1. `/api/v1/chat/turn` receives `campaign_id` and `user_input` (`actor_id` optional).
2. `TurnService` loads the campaign from file storage.
3. If `actor_id` is not provided, `active_actor_id` is used for this turn.
4. The LLM output provides `dialog_type`; missing/invalid values fall back to
   `DEFAULT_DIALOG_TYPE`.
5. `LLMClient` returns JSON with `assistant_text`, `dialog_type`, and `tool_calls`.
6. A turn log entry is appended to `turn_log.jsonl`.
7. The API responds with narrative text, dialog type, and state summary.

## Turn Request Shape

`POST /api/v1/chat/turn` requires `campaign_id` and `user_input`. `actor_id` is
optional and defaults to the campaign's `active_actor_id`.

```json
{
  "campaign_id": "camp_0001",
  "user_input": "I light a torch.",
  "actor_id": "pc_001"
}
```
