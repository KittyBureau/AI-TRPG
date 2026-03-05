# Debug Trace Contract (Runtime)

## Status

- `Implemented`: trace gate and payload structure are active in runtime.
- `Planned`: no additional planned fields are required for Playable v1.

## Trace Gate

Trace is controlled per campaign via settings:

- key: `dialog.turn_profile_trace_enabled`
- default: `false`

When disabled, turn response omits top-level `debug`.

Enable trace:

```json
POST /api/v1/settings/apply
{
  "campaign_id": "camp_0001",
  "patch": {
    "dialog.turn_profile_trace_enabled": true
  }
}
```

## Primary Contract: `debug.resources`

For `POST /api/v1/chat/turn`, when trace is enabled:

- `debug.resources.prompts[]`
- `debug.resources.flows[]`
- `debug.resources.schemas[]`
- `debug.resources.templates[]`
- `debug.resources.policies[]`
- `debug.resources.template_usage[]`

All categories are arrays (possibly empty).

## Legacy Compatibility Fields (Still Emitted)

Runtime still emits legacy fields for backward compatibility:

- flat fields: `debug.used_prompt_*`, `debug.used_flow_*`, `debug.used_profile_hash`, optional `debug.used_profile_version`
- nested fields: `debug.prompt`, `debug.flow`, `debug.schemas`, `debug.templates`
- template usage compatibility: `debug.template_usage`

Frontend debug viewer supports both sources:

- prefers `debug.resources`
- falls back to legacy fields when `debug.resources` is absent

## Reference JSON Example

```json
{
  "debug": {
    "used_profile_hash": "...",
    "used_prompt_name": "turn_profile_default",
    "used_prompt_version": "v1",
    "used_flow_name": "play_turn_basic",
    "used_flow_version": "v1",
    "resources": {
      "prompts": [],
      "flows": [],
      "schemas": [],
      "templates": [],
      "policies": [],
      "template_usage": []
    },
    "prompt": {},
    "flow": {},
    "schemas": [],
    "templates": []
  }
}
```

## Validation / Regression

- Contract schema: `resources/schemas/debug_resources_v1.schema.json`
- Tests:
  - `backend/tests/test_debug_resources_contract_schema.py`
  - `backend/tests/test_turn_service_lifecycle.py`
- Manual guide:
  - `docs/20_runtime/testing/api_test_guide.md`
  - `docs/02_guides/testing/playable_v1_manual_test.md`
