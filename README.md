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
