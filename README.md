# DocumentsAndDirectives

Minimal backend scaffolding for the AI TRPG prototype.

## Start

1. Create a virtual environment and install dependencies (FastAPI + Uvicorn).
2. Run the API:

```bash
uvicorn backend.api.main:app --reload
```

## LLM Configuration

1. Copy `storage/config/llm_config.example.json` to `storage/config/llm_config.json`.
2. Edit `current_profile` and profile fields as needed.
3. On first `/api/chat/turn`, the server will prompt for an API key and a local passphrase
   (both via stdin with no echo). The key is stored encrypted in `storage/secrets/keyring.json`.
4. The keyring uses AES-GCM via the `cryptography` package.

## Docs

- `docs/README.md` for the documentation index.
- `docs/01_architecture.md` for layer overview and request shape.
- `docs/02_storage_layout.md` for storage layout and JSON schemas.
