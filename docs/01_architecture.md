# Architecture Overview (Stage 1)

This backend is organized by layers to keep authority boundaries clear and enable
incremental delivery.

## Layers

- `backend/api/`: FastAPI transport only. Maps HTTP to application services.
- `backend/app/`: Turn orchestration. Coordinates classifier, FakeLLM, and storage.
- `backend/domain/`: Pure domain rules (dialog type classifier, models).
- `backend/infra/`: File storage and FakeLLM implementation.
- `storage/`: Local persistence rooted at the workspace.

## Stage 1 Data Flow

1. `/api/chat/turn` receives `campaign_id` and `user_input` (`actor_id` optional).
2. `TurnService` loads the campaign from file storage.
3. If `actor_id` is not provided, `active_actor_id` is used for this turn.
4. `DialogTypeClassifier` assigns `dialog_type` by rules.
5. `FakeLLM` echoes the input and returns empty `tool_calls`.
6. A turn log entry is appended to `turn_log.jsonl`.
7. The API responds with narrative text, dialog type, and state summary.

## Turn Request Shape

`POST /api/chat/turn` requires `campaign_id` and `user_input`. `actor_id` is
optional and defaults to the campaign's `active_actor_id`.

```json
{
  "campaign_id": "camp_0001",
  "user_input": "I light a torch.",
  "actor_id": "pc_001"
}
```
