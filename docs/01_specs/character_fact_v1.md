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
- Test-backed baseline behavior is split:
  - normalize path drops unknown `meta` keys.
  - strict read validation may reject unknown `meta` keys.

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
  - `character_id` is always an allocated real ID (`__AUTO_ID__` is never persisted).
- Adoption sidecar file:
  - `storage/campaigns/{campaign_id}/characters/generated/{character_id}.fact.accepted.json`
  - stores adoption metadata only; CharacterFact payload remains schema-frozen.

### Batch file structure (frozen)

```json
{
  "schema_id": "character_fact.v1",
  "schema_version": "1",
  "campaign_id": "camp_0001",
  "request_id": "req_001",
  "utc_ts": "20260210T153000Z",
  "params": {},
  "items": []
}
```

### Individual draft structure (frozen)

- Single `CharacterFact` JSON object only.

## 6. Request id and timestamp conventions

- `request_id`:
  - default convention: `req_<slug>`
  - characters allowed in filename context: letters, digits, `_`, `-`
  - uniqueness scope: per `campaign_id`; duplicate submit returns `409 Conflict`
- `utc_ts` format:
  - `YYYYMMDDTHHMMSSZ`
  - example: `20260210T153000Z`

## 7. CharacterFact API endpoints (`/api/v1`)

- `POST /api/v1/campaigns/{campaign_id}/characters/generate`
  - generates draft+normalize output, validates schema, allocates IDs, persists batch+individual files
  - response returns references only:
    - `campaign_id`
    - `request_id`
    - `batch_path`
    - `individual_paths`
    - `count_requested`
    - `count_generated`
    - `warnings`
- `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches`
- `GET /api/v1/campaigns/{campaign_id}/characters/generated/batches/{request_id}`
- `GET /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}`
- `POST /api/v1/campaigns/{campaign_id}/characters/facts/{character_id}/adopt`
  - writes static profile data into `campaign.actors[*].meta.profile`
  - writes adoption metadata to sidecar
  - must not overwrite runtime fields (`position`, `hp`, `character_state`)

## 8. Test-backed behavior freeze (Guaranteed vs Unspecified)

The entries below are derived from tests only. Anything not listed as Guaranteed is Unspecified.

### 8.1 GET `/facts/{character_id}`

| Status | Case | Expected behavior | Test evidence |
| --- | --- | --- | --- |
| Guaranteed | draft exists and is valid | return `200` with draft payload | `backend/tests/test_character_fact_api.py:250` |
| Guaranteed | draft missing, batch has the character | return `200` via batch fallback | `backend/tests/test_character_fact_api.py:250` |
| Guaranteed | draft file unreadable JSON, batch has the character | return `200` via batch fallback | `backend/tests/test_character_fact_api.py:282` |
| Guaranteed | draft is readable JSON but schema-invalid (`meta.unknown`) | return `422` (no fallback in this case) | `backend/tests/test_character_fact_api.py:308` |
| Unspecified | draft missing and batch also missing | status/shape are not frozen by tests | not asserted |
| Unspecified | campaign missing for GET fact | status/shape are not frozen by tests | not asserted |
| Unspecified | conflict between draft and batch payload contents | precedence details are not frozen by tests | not asserted |

### 8.2 POST `/characters/generate` error precedence

| Status | Case | Expected behavior | Test evidence |
| --- | --- | --- | --- |
| Guaranteed | valid request | return `200` refs-only payload (`batch_path`, `individual_paths`, `count_requested`, `count_generated`, `warnings`) | `backend/tests/test_character_fact_api.py:85` |
| Guaranteed | same `campaign_id` + same `request_id` resubmitted | return `409`; no new batch file | `backend/tests/test_character_fact_api.py:128` |
| Guaranteed | `tone_vocab_only=true` and `allowed_tones=[]` with existing campaign | return `400` | `backend/tests/test_character_fact_api.py:156` |
| Guaranteed | normalize output becomes schema-invalid | return `422` | `backend/tests/test_character_fact_api.py:189` |
| Guaranteed | campaign missing + payload also has `allowed_tones=[]` | return `404` (campaign check precedence over this `400`) | `backend/tests/test_character_fact_api.py:173` |
| Unspecified | conflict + schema-invalid generated output in one request | precedence is not frozen by tests | not asserted |
| Unspecified | campaign missing + any other parameter error combination | precedence beyond the case above is not frozen by tests | not asserted |
