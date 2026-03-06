# Conflict Guard & Debug Retry (Stage 4)

Stage 4 integrates a real LLM and introduces conflict detection with limited
debug retries. Authoritative state always wins.

## LLM Client

The LLM client uses an OpenAI-compatible `chat/completions` endpoint with a
JSON response format. Configuration is loaded from:

- `storage/config/llm_config.json` (current_profile + profiles)
- `storage/secrets/keyring.json` (encrypted API keys)

The keyring remains local-file based with no environment-variable fallback.
Runtime startup is non-interactive: it only checks config/keyring readiness.
If runtime status reports `passphrase_required`, unlock the running backend with:

```bash
python -m backend.tools.unlock_keyring
```

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

- `state_mismatch`: tool execution indicates no change, but authoritative state changes.
- `tool_result_mismatch`: tool execution results do not match authoritative state.
- `forbidden_change`: narrative attempts to change rules, maps, or world data (text checks only).

Text-based checks are disabled by default.

- Global env gate: `CONFLICT_TEXT_CHECKS=1`
- Campaign gate: `settings_snapshot.dialog.conflict_text_checks_enabled=true`

Text checks execute when either gate is enabled. When enabled,
`dialog_type=rule_explanation` only evaluates `forbidden_change`.

Example conflict report:

```json
{
  "conflicts": [
    {
      "type": "tool_result_mismatch",
      "field": "hp_delta",
      "expected": 0,
      "found_in_text": "10"
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

## Repeat illegal request suppression (V1.1)

- Runtime inspects recent 3 turn logs and computes a signature from `tool+args`.
- If the same signature was repeatedly failed in each of those turns, the new
  request is suppressed before tool execution.
- Suppressed calls are reported via `tool_feedback.failed_calls[*].reason`:
  - `repeat_illegal_request`
- V1.1 keeps single-process semantics; no file lock strategy is applied yet.

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
