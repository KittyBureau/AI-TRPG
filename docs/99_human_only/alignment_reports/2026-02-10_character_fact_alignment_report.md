# Character Fact Alignment Report (2026-02-10)

Scope: role-data generation alignment and prompt-template planning, based on current repository facts.

## 1. Alignment Checklist

| Item | Exists | Path | Key Fields / Classes / Functions | Constraints Summary |
| --- | --- | --- | --- | --- |
| Architecture spec | Yes | `docs/01_specs/architecture.md` | Layer boundaries; `TurnService.submit_turn` in `backend/app/turn_service.py` | API/app/domain/infra boundaries are fixed; critical character state paths should use `CharacterFacade`. |
| Storage layout spec | Yes | `docs/01_specs/storage_layout.md` | `Campaign`, `ActorState`, `StateSummary`, `TurnLogEntry` in `backend/domain/models.py` | Runtime authority is `campaign.actors`; legacy mirrors (`positions/hp/character_states`) remain compatibility maps. |
| Tools spec | Yes | `docs/01_specs/tools.md` | `execute_tool_calls`, `_apply_move` in `backend/app/tool_executor.py` | `move` does not accept `from_area_id`; `to_area_id` required; `actor_id` optional (defaults to active actor). |
| Dialog types spec | Yes | `docs/01_specs/dialog_types.md` | `DIALOG_TYPES`, `DEFAULT_DIALOG_TYPE` in `backend/domain/dialog_rules.py`; `_resolve_dialog_type` in `backend/app/turn_service.py` | LLM output keys: `assistant_text`, `dialog_type`, `tool_calls`; invalid dialog type falls back. |
| Character access boundary | Yes | `docs/01_specs/character_access_boundary.md` | `CharacterState`, `CharacterFact`, `CharacterView`, `CharacterFacade` in `backend/domain/character_access.py` | Use facade boundary; keep current `campaign.json` authority and behavior. |
| Character baseline | Yes | `docs/01_specs/character_baseline.md` | Existing API/actor data baseline entries in doc | Character generation module is still a gap; current system focuses on campaign-runtime actors. |

## 2. CharacterFact JSON Schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://ai-trpg.local/schemas/character_fact.v1.json",
  "title": "CharacterFact",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "character_id",
    "name",
    "role",
    "tags",
    "attributes",
    "background",
    "appearance",
    "personality_tags"
  ],
  "properties": {
    "character_id": {
      "type": "string",
      "minLength": 3,
      "maxLength": 64,
      "pattern": "^[a-zA-Z][a-zA-Z0-9_-]*$",
      "description": "Unique character ID."
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 80,
      "description": "Display name."
    },
    "role": {
      "type": "string",
      "minLength": 1,
      "maxLength": 40,
      "description": "Role/class archetype."
    },
    "tags": {
      "type": "array",
      "description": "Static tags. Deduplicated.",
      "default": [],
      "maxItems": 8,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 24
      }
    },
    "attributes": {
      "type": "object",
      "description": "Static attribute bag only (no runtime state).",
      "default": {},
      "additionalProperties": {
        "type": [
          "string",
          "number",
          "boolean"
        ]
      }
    },
    "background": {
      "type": "string",
      "description": "Background summary.",
      "default": "",
      "maxLength": 400
    },
    "appearance": {
      "type": "string",
      "description": "Appearance summary.",
      "default": "",
      "maxLength": 240
    },
    "personality_tags": {
      "type": "array",
      "description": "Personality tags. Deduplicated.",
      "default": [],
      "maxItems": 8,
      "uniqueItems": true,
      "items": {
        "type": "string",
        "minLength": 1,
        "maxLength": 24
      }
    },
    "meta": {
      "type": "object",
      "description": "Extension slot for future compatibility.",
      "default": {},
      "additionalProperties": true,
      "properties": {
        "hooks": {
          "type": "array",
          "default": [],
          "maxItems": 5,
          "uniqueItems": true,
          "items": {
            "type": "string",
            "minLength": 1,
            "maxLength": 80
          }
        },
        "language": {
          "type": "string",
          "default": "zh-CN"
        },
        "source": {
          "type": "string",
          "default": "llm"
        }
      }
    }
  }
}
```

## 3. Prompt Template (System / User / Output)

### A. System Template

```text
You are generating CHARACTER FACT profiles for an AI-TRPG system.

Rules:
1) Output MUST be valid JSON and MUST conform to the provided CharacterFact JSON Schema.
2) Output ONLY static profile data.
3) DO NOT output runtime fields: position, hp, character_state.
4) Keep style consistent with:
   - language: {{language}}
   - tone: {{tone_style}}
5) Avoid direct duplication/conflict with existing party context.
6) No markdown, no explanation text outside JSON.

Schema:
{{character_fact_schema_json}}
```

### B. User Template

```json
{
  "campaign_tone": [
    "grim",
    "mystery",
    "low-magic"
  ],
  "setting_seed": [
    "frontier city",
    "ancient ruins",
    "faction conflict"
  ],
  "party_context": [
    {
      "character_id": "pc_001",
      "name": "Ava",
      "role": "scout",
      "summary": "fast recon specialist",
      "tags": [
        "stealth",
        "urban"
      ]
    }
  ],
  "constraints": {
    "allowed_roles": [
      "scout",
      "guardian",
      "speaker",
      "mystic"
    ],
    "forbidden_roles": [
      "demigod"
    ],
    "style_notes": "grounded, no comedy names",
    "name_locale": "zh-CN"
  },
  "count": 3,
  "id_policy": "system"
}
```

### C. Output Rule

```text
Return JSON array only:
[
  {CharacterFact},
  {CharacterFact}
]

If id_policy=system:
- set character_id to "__AUTO_ID__".

If id_policy=model:
- generate stable unique IDs.
```

## 4. Two-Phase Prompt

### 4.1 Draft Prompt

```text
Task: Generate initial CharacterFact drafts.

Input:
{{user_payload_json}}

Requirements:
- Return JSON array only.
- Each item must follow CharacterFact schema core fields.
- Do not include runtime fields: position, hp, character_state.
- Keep distinct roles/names across generated items.
- Respect constraints and party_context.
```

### 4.2 Normalize / Validate Prompt

```text
Task: Normalize and validate CharacterFact drafts.

Input:
1) Draft JSON array
2) CharacterFact JSON Schema
3) party_context + constraints

Rules:
- Keep JSON array only; no prose.
- Remove fields not in schema.
- Fill missing required fields with schema defaults.
- Enforce limits:
  - name <= 80
  - role <= 40
  - tags/personality_tags item length <= 24, max 8 items
  - meta.hooks item length <= 80, max 5 items
- Deduplicate tags/personality_tags/hooks.
- Remove tags/personality_tags conflicting with party_context.
- Ensure character_id uniqueness in output.
- Keep runtime fields forbidden.
```

## 5. Temporary Persistence Path Suggestion

- `storage/campaigns/{campaign_id}/characters/generated/batch_{utc_ts}_{request_id}.json`
- `storage/campaigns/{campaign_id}/characters/generated/{character_id}.fact.draft.json`
- Future target:
  - `storage/characters_library/{character_id}.json`
  - `storage/campaigns/{campaign_id}/characters/{character_id}.fact.json`
  - `storage/campaigns/{campaign_id}/characters/{character_id}.state.json`

Naming examples:
- `batch_20260210T153000Z_req_001.json`
- `pc_003.fact.draft.json`
- `pc_003.fact.json`
- `pc_003.state.json`

Compatibility rule:
- Do not change turn/tool protocol while introducing these files.
- Keep campaign runtime authority unchanged until adapter switch.

## 6. NOW / TODO

- `NOW`: alignment checklist and constraints summary.
- `NOW`: CharacterFact JSON schema and prompt templates.
- `NOW`: two-phase draft/normalize prompting design.
- `NOW`: temporary persistence path proposal compatible with current campaign flow.
- `TODO`: generate/save APIs and library management UI.
- `TODO`: production validator pipeline and ID allocator integration.
