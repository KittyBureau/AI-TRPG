# CharacterFact v1 Spec Freeze

This document freezes schema versioning, prompt protocol, and persistence protocol for CharacterFact v1.

## 1. Scope

- Character generation outputs static `CharacterFact` only.
- Runtime state authority remains `campaign.actors`.
- Turn/tool protocol is unchanged.

## 2. Schema freeze

- Schema file: `docs/01_specs/schemas/character_fact.v1.schema.json`
- Version token: `character_fact.v1`
- Required fields:
  - `character_id`
  - `name`
  - `role`
  - `tags`
  - `attributes`
  - `background`
  - `appearance`
  - `personality_tags`
- `additionalProperties` is `false`.
- Runtime fields are forbidden in facts:
  - `position`
  - `hp`
  - `character_state`

### Version evolution rule

- Backward-compatible additions can go to `v1.x` docs only if they do not change required/forbidden behavior.
- Breaking changes (required fields, field semantics, constraints, forbidden list) require a new schema file:
  - `character_fact.v2.schema.json`
- Prompt protocol must reference the schema version explicitly.

## 3. Meta extension rule

- `meta_extension_policy = predefined-only`
- Allowed `meta` keys:
  - `hooks`
  - `language`
  - `source`
- Any other `meta` keys are rejected in normalize/persistence.

## 4. Prompt protocol freeze

- Prompt spec file: `docs/01_specs/prompts/character_fact_generate_v1.md`
- Prompt management mode: `structured`
- Validation pipeline: `draft+normalize`
- Conflict policy: `tag_conflict_policy=allow`
  - Normalize does not perform party overlap semantic trimming.
  - Normalize still enforces schema, limits, per-character dedup, and id uniqueness.

## 5. Persistence protocol freeze

Generated files are non-authoritative temporary artifacts:

- Batch file:
  - `storage/campaigns/{campaign_id}/characters/generated/batch_{utc_ts}_{request_id}.json`
- Individual draft file:
  - `storage/campaigns/{campaign_id}/characters/generated/{character_id}.fact.draft.json`
  - If `character_id="__AUTO_ID__"`, a temporary filename-safe id is used.

### Batch file structure (frozen)

```json
{
  "schema_version": "character_fact.v1",
  "request_id": "req_001",
  "campaign_id": "camp_0001",
  "generated_at": "2026-02-10T12:00:00Z",
  "config_snapshot": {},
  "request_snapshot": {},
  "items": []
}
```

### Individual draft structure (frozen)

- Single `CharacterFact` JSON object only.

## 6. Request id and timestamp conventions

- `request_id`:
  - default convention: `req_<slug>`
  - characters allowed in filename context: letters, digits, `_`, `-`
- `utc_ts` format:
  - `YYYYMMDDTHHMMSSZ`
  - example: `20260210T153000Z`
