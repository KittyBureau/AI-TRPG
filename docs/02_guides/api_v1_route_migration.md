# API v1 Route Prefix Migration

Date: 2026-02-10

## Summary

HTTP routes are versioned under `/api/v1`.

- Old style: `/api/<module>/...`
- New style: `/api/v1/<module>/...`

OpenAPI/docs are aligned to the same base path:

- OpenAPI: `/api/v1/openapi.json`
- Docs: `/api/v1/docs`
- ReDoc: `/api/v1/redoc`

## Mapping

- `/api/campaign/create` -> `/api/v1/campaign/create`
- `/api/campaign/list` -> `/api/v1/campaign/list`
- `/api/campaign/select_actor` -> `/api/v1/campaign/select_actor`
- `/api/campaign/status` -> `/api/v1/campaign/status`
- `/api/campaign/milestone/advance` -> `/api/v1/campaign/milestone/advance`
- `/api/chat/turn` -> `/api/v1/chat/turn`
- `/api/map/view` -> `/api/v1/map/view`
- `/api/settings/schema` -> `/api/v1/settings/schema`
- `/api/settings/apply` -> `/api/v1/settings/apply`
- `/api/campaigns/{campaign_id}/characters/generate` -> `/api/v1/campaigns/{campaign_id}/characters/generate`
- `/api/campaigns/{campaign_id}/characters/generated/batches` -> `/api/v1/campaigns/{campaign_id}/characters/generated/batches`
- `/api/campaigns/{campaign_id}/characters/generated/batches/{request_id}` -> `/api/v1/campaigns/{campaign_id}/characters/generated/batches/{request_id}`
- `/api/campaigns/{campaign_id}/characters/facts/{character_id}` -> `/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}`
- `/api/campaigns/{campaign_id}/characters/facts/{character_id}/adopt` -> `/api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt`

## Notes

- This migration changes routing only.
- Existing route payload contracts remain backward compatible.
- New v1 routes were added for lifecycle observability and CharacterFact adoption.
