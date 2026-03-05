# External Resources and Trace Status

## Scope

This document is the runtime-aligned status for external resource loading in this repo.

Status labels used below:

- `Implemented`: behavior exists in current code.
- `Planned`: design goal only, not executing in runtime yet.

## Implemented

### 1. Resource manifest structure

Implemented in `resources/manifest.json` with these sections:

- `prompts`
- `flows`
- `schemas`
- `templates`
- `policies`

Each resource entry uses a single object or a version list, with required runtime loader keys:

- `version`
- `path` (must be relative and start with `resources/`)
- `enabled` (exactly one enabled for prompt/flow/schema/template loaders)

Current manifest also carries governance metadata like `hash`.

### 2. Loader behavior and validation

Implemented in `backend/infra/resource_loader.py`.

Prompt/flow/schema/template loaders (`load_enabled_*`) enforce:

- manifest exists and is valid JSON object
- target section exists and is object
- named resource exists
- resource entry shape is valid (`version/path/enabled`)
- exactly one enabled entry
- file exists
- payload format checks:
  - prompt: non-empty text
  - flow/schema/template: valid JSON object
  - flow additionally requires `id`, `version`, `steps`

### 3. Policy fallback behavior

Implemented in `load_enabled_policy`.

If manifest or policy entry is missing/invalid/multi-enabled/file-invalid, loader falls back to builtin policy metadata:

- fallback path: `builtin://policy/<name>`
- `fallback=true` in loaded metadata

Builtin `turn_tool_policy` descriptor exists and includes allowlist/retry/conflict metadata notes.

### 4. Hash behavior

Implemented hash outputs:

- prompt hash: SHA-256 of text content
- flow/schema/template/policy hash: SHA-256 of canonical JSON (`sort_keys=True`, compact separators)

Current runtime uses hashes for trace/observability metadata. Hash mismatch does **not** block runtime loading by itself.

### 5. Trace gate and debug payload

Trace gate is implemented via setting:

- `dialog.turn_profile_trace_enabled` (default `false`)

When `false`:

- `/api/v1/chat/turn` has no top-level `debug`

When `true`:

- `/api/v1/chat/turn` includes `debug` with primary contract at `debug.resources`
- resource categories in `debug.resources`:
  - `prompts`
  - `flows`
  - `schemas`
  - `templates`
  - `policies`
  - `template_usage`

Legacy compatibility fields are still emitted:

- `debug.used_prompt_*`, `debug.used_flow_*`
- `debug.prompt`, `debug.flow`, `debug.schemas`, `debug.templates`

### 6. Template-usage debug in create/upsert paths

Implemented for endpoints that apply templates:

- `POST /api/v1/campaign/create`
- `POST /api/v1/characters/library`

Debug payload uses `resources.template_usage` and keeps legacy `debug.template_usage` compatibility field.

## Example debug.resources shape (trace enabled)

```json
{
  "debug": {
    "resources": {
      "prompts": [
        {
          "name": "turn_profile_default",
          "version": "v1",
          "source_hash": "...",
          "rendered_hash": "...",
          "fallback": false
        }
      ],
      "flows": [
        {
          "name": "play_turn_basic",
          "version": "v1",
          "hash": "...",
          "fallback": false
        }
      ],
      "schemas": [],
      "templates": [],
      "policies": [],
      "template_usage": []
    }
  }
}
```

## Planned (Not Implemented Yet)

- Executing turn behavior directly from externalized flow definitions.
- Runtime hard-fail enforcement on manifest `hash` mismatch.
- Resource hot-reload while process is running.
- Campaign-level resource overrides and A/B routing.

## Verification Entry Points

- Unit tests:
  - `backend/tests/test_resources_manifest_hashes.py`
  - `backend/tests/test_policy_resource_loader.py`
  - `backend/tests/test_turn_service_lifecycle.py`
  - `backend/tests/test_debug_resources_contract_schema.py`
- Manual/API checks:
  - `docs/20_runtime/testing/api_test_guide.md`
  - `docs/02_guides/testing/playable_v1_manual_test.md`

## Migration Note

Legacy planning path:

- `docs/03_architecture/external_resources_todo.md` (redirect stub)

Authoritative path:

- `docs/30_resources/external_resources_and_trace.md`
