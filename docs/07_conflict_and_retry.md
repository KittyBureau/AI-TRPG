# Conflict Guard & Debug Retry (Stage 4)

Stage 4 integrates a real LLM and introduces conflict detection with limited
debug retries. Authoritative state always wins.

## LLM Client

The LLM client uses an OpenAI-compatible `chat/completions` endpoint with a
JSON response format. Configuration is read from environment variables:

- `LLM_BASE_URL` (default `https://api.openai.com/v1`)
- `LLM_API_KEY` (required)
- `LLM_MODEL` (default `gpt-4o-mini`)
- `LLM_TEMPERATURE` (default `0.2`)

The model must return a JSON object:

```json
{
  "assistant_text": "Narrative response",
  "dialog_type": "scene_description",
  "tool_calls": [
    { "id": "call_001", "tool": "move", "args": {}, "reason": "..." }
  ]
}
```

## Conflict Types (minimal)

Conflicts are detected before logging and can trigger retries:

- `state_mismatch`: narrative claims state changes without applied actions.
- `tool_result_mismatch`: narrative implies success while tool calls failed.
- `forbidden_change`: narrative attempts to change rules, maps, or world data.

When `dialog_type` is `rule_explanation`, only `forbidden_change` is evaluated.

Example conflict report:

```json
{
  "has_conflict": true,
  "conflicts": [
    {
      "type": "state_mismatch",
      "field": "hp.pc_001",
      "expected": 0,
      "found_in_text": "still healthy"
    }
  ]
}
```

## Debug Append + Retry

On conflict:

1. Do not write turn_log.
2. Append a system debug message describing conflicts and authoritative state.
3. Retry with the same user input (max retries = 2).

If retries are exhausted, return `conflict_report` and do not persist changes or logs.

## TurnLog Conflict Report

If a turn succeeds after retries, a `conflict_report` is stored in the turn log:

```json
{
  "retries": 1,
  "conflicts": [
    { "type": "state_mismatch", "field": "positions", "expected": "no_change", "found_in_text": "moved" }
  ]
}
```
