# AI-TRPG

Minimal backend + frontend prototype for AI-assisted TRPG flow.

## Version

- Project version: `1.0`

## Start

1. Create a virtual environment and install dependencies.
2. Run the API:

```bash
uvicorn backend.api.main:app --reload
```

## LLM Configuration

1. Copy `storage/config/llm_config.example.json` to `storage/config/llm_config.json`.
2. Edit `current_profile` and profile settings.
3. On first `POST /api/v1/chat/turn`, the server prompts for API key and passphrase via stdin.
4. Encrypted key is written to `storage/secrets/keyring.json` (AES-GCM via `cryptography`).

## Documentation Entry

- Main docs index: `docs/00_overview/README.md`
- AI task index: `docs/_index/AI_INDEX.md`

## Documentation Workflow

- Primary workflow: local VSCode + Codex with the full repository as source of truth.
- ChatGPT web project context uses a lightweight Google Drive reference-doc package refreshed via `scripts/sync_chatgpt_docs.ps1`.
- That package is intentionally small and stage-oriented; detailed implementation lookup should still happen from the local repo, usually through Codex.
- Current item-system/runtime truth is stack-first: portable item authority is `campaign.items`, frontend inventory authority derives from stack payloads, and `selected_stack_id` is the normal selection/submit path.

## Current Runtime Truth

- Core portable-item loop is `search -> reveal -> take`.
- `campaign.items` is the authoritative portable-item store.
- `actors[*].inventory` is a derived compatibility view only.
- `search` does not grant possession; actor ownership changes on `take`.
- Gate checks still use `required_item_id` rules, but possession evidence comes from actor-owned stacks derived from `campaign.items`.
- `inventory_add` still exists as a bounded legacy-only contract for source-entity-backed inventory gain; it is not the mainline gameplay path.
- Formal Gameplay Model v0 is a read-only structural validation layer for generated scenarios and the current baseline presets.
- It does not affect turn execution, tool execution, or runtime authority.

## Current Item Docs

- Runtime truth: `docs/20_runtime/item_runtime_model.md`
- Persistence truth: `docs/20_runtime/storage_authority.md`
- Tool contract details: `docs/01_specs/tools.md`
