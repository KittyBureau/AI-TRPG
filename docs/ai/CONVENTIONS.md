# Conventions

## Directory conventions
- `backend/app/` - FastAPI entrypoints and route wiring.
- `backend/services/` - Business logic and tool behavior.
- `backend/storage/worlds/` - Versioned static world data.
- `backend/storage/runs/` - Dynamic state and facts (sample data allowed).
- `frontend/public/` - Static UI assets.
- `docs/ai/` - AI index system and repo-wide standards.
- `docs/ai-trpg/` - Domain design/spec docs.

Gitignored (local-only) directories:
- `data/`
- `backend/data/`
- `backend/logs/`

## Naming conventions
- Python modules/functions: `snake_case`.
- Python classes: `PascalCase`.
- JSON file names: `snake_case` (example: `sample_world.json`).
- ID prefixes: `loc_*`, `pc_*` (extend as needed).
- Movement path_id: `loc_a->loc_b->loc_c` (stable signature).

## Logging and error handling
- Services raise domain exceptions; API layer maps to JSON errors.
- Error response pattern: `{"status":"ERROR","message":"..."}`.
- Logging framework: ??? (default: Python `logging` with module-level logger).

## Configuration and environment
- Required: `%USERPROFILE%\.ai-trpg\secrets.enc` (encrypted) and `%USERPROFILE%\.ai-trpg\config.json`.
- Additional config files: ??? (default: JSON under user profile or `backend/storage/` template).

## Data persistence rules
- Versioned samples and fixtures go under `backend/storage/`.
- Runtime outputs go under gitignored directories.
- Do not commit secrets or `.env` files. Keep `secrets.enc` local-only.
