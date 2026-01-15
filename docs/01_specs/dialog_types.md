# Dialog Types (Stage 4)

## Types

- `scene_description`
- `action_prompt`
- `resolution_summary`
- `rule_explanation`

Enum source: `backend/domain/dialog_rules.py` (`DIALOG_TYPES`).

## Model Output

Dialog type is provided by the LLM output. The system accepts only the enumerated
values above. Missing or invalid values fall back to `scene_description`.

## Source Field

Each turn log stores `dialog_type_source`:

- `model`: dialog type came from the model output.
- `fallback`: missing/invalid dialog type, default applied.

## Examples

- "How does initiative work?" -> `rule_explanation`
- "Summarize what happened so far." -> `resolution_summary`
- "I open the door." -> `action_prompt`
- "The room is quiet and cold." -> `scene_description`
