# Frontend Entrypoints (Runtime)

## Current Entry Policy

- Recommended gameplay entry: `frontend/play.html`
- Recommended debug entry: `frontend/debug.html`
- Deprecated landing/redirect only: `frontend/index.html`

`frontend/index.html` should not be used for gameplay validation; it auto-redirects to Play UI.

## Panel Architecture

Current runtime frontend is panel-based and module-driven:

- state: `frontend/store/store.js`
- network API: `frontend/api/api.js`
- panel registry: `frontend/panels/registry.js`
- play bootstrap: `frontend/play.js`
- debug bootstrap: `frontend/debug.js`

Play page panels:

- Campaign Panel
- Character Library Panel
- Party Panel
- Actor Control Panel
- Debug Panel

## Validation Entry

Deterministic smoke scripts:

- `scripts/smoke_frontend_flow.ps1`
- `scripts/smoke_full_gameplay.ps1`

Related guide:

- `docs/20_runtime/gameplay_flow.md`
- `docs/20_runtime/testing/active_actor_integration_smoke.md`
- `docs/20_runtime/testing/state_consistency_check.md`
