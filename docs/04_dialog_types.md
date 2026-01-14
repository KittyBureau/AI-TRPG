# Dialog Types (Stage 2)

## Types

- `scene_description`
- `action_prompt`
- `resolution_summary`
- `rule_explanation`

## Rule-Based Classification

Dialog type classification uses a rule engine (not LLM). Rules are defined in
`backend/domain/dialog_rules.py` and can be updated without changing the
classifier implementation.

When `dialog.auto_type_enabled` is `false`, the classifier always returns the
default type (`scene_description`) and records source as `fixed`.

Default ordering:

1. `rule_explanation`
2. `resolution_summary`
3. `action_prompt`
4. fallback: `scene_description`

## Source Field

Each turn log stores `dialog_type_source`:

- `auto`: rules were applied (including fallback).
- `fixed`: `dialog.auto_type_enabled` was `false`, so a fixed default type was used.

## Examples

- "How does initiative work?" -> `rule_explanation`
- "Summarize what happened so far." -> `resolution_summary`
- "I open the door." -> `action_prompt`
- "The room is quiet and cold." -> `scene_description`
