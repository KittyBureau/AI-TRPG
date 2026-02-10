# CharacterFact Generate Prompt Protocol (v1)

This document freezes the prompt contract for CharacterFact generation.

## Fixed runtime decisions (v1)

```yaml
generation_mode: "batch"
id_policy: "system"
output_language_mode: "single"
default_language: "zh-CN"
tone_vocab_only_flag: true
role_policy: "allowlist"
tag_conflict_policy: "allow"
attribute_strictness: "open"
hook_generation_mode: "typed"
count_policy:
  default: 3
  max: 20
validation_pipeline: "draft+normalize"
persistence_style: "batch+individual"
conflict_types: ["name", "tags", "role", "personality_tags"]
prompt_management: "structured"
meta_extension_policy: "predefined-only"
```

## System template

```text
You are generating CHARACTER FACT profiles for an AI-TRPG system.

Hard Rules:
1) Output MUST be valid JSON and MUST conform to the provided CharacterFact JSON Schema.
2) Output ONLY static profile data.
3) DO NOT output runtime fields: position, hp, character_state (for any reason).
4) No markdown and no explanation text outside JSON.

Style Parameters:
- language: {{language}} (default zh-CN)
- tone_style: {{tone_style}}
- tone_vocab_only: {{tone_vocab_only}} (boolean)
  If true, you may ONLY use tones from allowed_tones.

Constraints:
- role_policy is allowlist: you may ONLY use roles from allowed_roles.
- id_policy: {{id_policy}}. If id_policy=system, set character_id to "__AUTO_ID__".
- tag_conflict_policy=allow: you MUST NOT modify content to avoid party overlap, except for fixing schema/format errors.

CharacterFact JSON Schema:
{{character_fact_schema_json}}
```

## User payload template

```json
{
  "language": "zh-CN",
  "tone_style": [
    "grim",
    "mystery",
    "low-magic"
  ],
  "tone_vocab_only": true,
  "allowed_tones": [
    "grim",
    "mystery",
    "low-magic"
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
    "style_notes": "grounded, no comedy names"
  },
  "count": 3,
  "max_count": 20,
  "id_policy": "system",
  "request_id": "req_001"
}
```

## Output rule

```text
Return JSON array only:
[
  {CharacterFact},
  {CharacterFact}
]

If id_policy=system:
- set character_id to "__AUTO_ID__" for every item.

Do NOT include any extra keys outside the schema.
Do NOT include runtime fields (position/hp/character_state).
```

## Draft prompt (phase 1)

```text
Task: Generate initial CharacterFact drafts.

Input:
{{user_payload_json}}

Requirements:
- Return JSON array only.
- Each item must follow CharacterFact schema required fields.
- No runtime fields: position, hp, character_state.
- Respect:
  - allowed_roles allowlist
  - tone_vocab_only + allowed_tones if enabled
  - count (cap at max_count)
- Keep names reasonably distinct within this batch.
```

## Normalize prompt (phase 2)

```text
Task: Normalize and validate CharacterFact drafts.

Input:
1) Draft JSON array
2) CharacterFact JSON Schema
3) user_payload_json (party_context + constraints)

Rules:
- Output JSON array only; no prose.
- Remove fields not in schema.
- Fill missing required fields using schema defaults where possible.
- Enforce limits:
  - name <= 80
  - role <= 40
  - tags/personality_tags: items <= 24 chars, max 8 items
  - background <= 400
  - appearance <= 240
  - meta.hooks: items <= 80 chars, max 5 items
- Deduplicate tags/personality_tags/hooks WITHIN THE SAME CHARACTER ONLY.
- Ensure character_id uniqueness in output:
  - if "__AUTO_ID__", keep as-is (system will replace later)
  - else ensure no duplicates in the batch
- Do NOT modify content to avoid overlap with party_context (tag_conflict_policy=allow).
- Runtime fields are forbidden.
```

## Parameter notes

- `tone_vocab_only`: when `true`, tone words are restricted to `allowed_tones`.
- `allowed_roles`: hard allowlist when role policy is `allowlist`.
- `count`: requested generation count.
- `max_count`: hard cap; backend clamps count to this limit.
- `language`: single language output mode in v1.
- `id_policy`: v1 defaults to `system` and uses `__AUTO_ID__` placeholders.
  Backend allocates final `character_id` values before writing files.
