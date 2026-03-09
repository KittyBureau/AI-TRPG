# P1-14 Closure Handoff

P1-14 now covers per-actor frontend selected-item state, optional `context_hints.selected_item_id` on turn requests, backend inventory validation, `selected_item` context injection, optional metadata enrichment from `resources/data/items_catalog_v1.json`, and trace-gated `debug.selected_item` observability.

Verified on 2026-03-09 with `pytest -q`, `node --experimental-default-type=module --test frontend/tests/store_loop.test.mjs`, `scripts/smoke_full_gameplay.ps1`, and `scripts/smoke_frontend_flow.ps1`.

Intentional limits: inventory authority remains `campaign.json.actors[*].inventory`, selected item is not persisted independently, missing/invalid metadata falls back to `{id, quantity}`, and there is no dedicated debug UI.

Recommended next task: P1-03 Map view scene entities consistency.
