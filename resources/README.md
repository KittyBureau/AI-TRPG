# External Resources Operations

This document defines the low-risk process for version switching and rollback of entries in `resources/manifest.json`.

## Add a New Version (Example: v2)

1. Add the new resource file under `resources/<kind>/...` (for example `resources/prompts/turn_profile_default_v2.txt`).
2. Compute hash with existing loader logic (recommended: run a small Python snippet using `backend.infra.resource_loader`).
3. In `resources/manifest.json`, append a new entry under the same resource name:
   - `version`
   - `path`
   - `hash`
   - `enabled` (set `false` first)
4. Keep only one `enabled: true` entry for each resource name.

## Switch Active Version

1. Set old entry `enabled: false`.
2. Set target entry `enabled: true`.
3. Run `pytest -q` (includes static manifest hash consistency checks).
4. Optional trace verification:
   - enable campaign trace (`turn_profile_trace_enabled=true`)
   - execute a turn / API path
   - verify `debug.resources` reports expected `name/version/hash`.

## Rollback

1. Flip manifest flags back to previous `enabled` entry.
2. Re-run `pytest -q`.
3. If needed, restore prior manifest from git history and verify trace metadata again.
