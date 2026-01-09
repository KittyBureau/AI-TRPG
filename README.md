# DocumentsAndDirectives

## Quick Start
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m backend.secrets.cli
python -m uvicorn backend.app.main:app --reload
```
Open: `http://127.0.0.1:8000/`

## Quick entrypoints
- Backend entry: `backend/app/main.py` (compat entry: `backend/main.py`)
- Frontend entry: `frontend/public/index.html`
- Character tool page: `/character`
- Character data directory (runtime, gitignored): `data/characters/`
- World data (versioned): `backend/storage/worlds/`
- World state/facts (sample): `backend/storage/runs/`

## Secrets + Config
- Encrypted secrets file: `%USERPROFILE%\.ai-trpg\secrets.enc`
- Plain config file: `%USERPROFILE%\.ai-trpg\config.json`
- Use `python -m backend.secrets.cli` to register keys and routing

## Routing Defaults
- `config.json` supports `routing.all` to apply one provider to all features.
- If a feature route is missing, `routing.all` is used as fallback.

## AI Documentation Index
- Required: before implementing context features, read `docs/TODO_CONTEXT.md`.
- `docs/ai/AI_INDEX.md` (entry point)
- `docs/ai/CONVENTIONS.md` (data placement + naming)
- `docs/ai/ARCHITECTURE.md` (current layering)
- `docs/ai-trpg/README.md` (domain docs)
- `docs/design/dialog_routing.md` (dialog routing + context profiles)
- `docs/testing/dialog_routing_test_method.md` (routing test method)

## Key modules
- `backend/services/llm_client.py`: /turn uses DeepSeek with strict JSON validation + retry
- `backend/services/character_service.py`: character generation, rename, and save (DeepSeek JSON + comment)
- `backend/services/world_movement.py`: movement paths + apply move
- `frontend/public/app.js`: index chat logic
- `frontend/public/character.js`: character tool UI logic

## Current structure
```text
.
  .venv/                # local virtual environment
  backend/
    app/                # app entry
      main.py
    services/           # business services
      llm_client.py
      character_service.py
      world_movement.py
    api/                # reserved
    agents/             # reserved
    core/               # reserved
    tools/              # reserved
    storage/            # JSON fixtures + sample state
      worlds/
      runs/
    prompts/            # prompt templates
    schemas/            # reserved
    tests/              # reserved
    scripts/            # reserved
    data/               # reserved
    logs/               # reserved
    requirements.txt
    README.md
    main.py             # compat entry
  frontend/
    public/
      index.html
      app.js
      style.css
      character.html
      character.js
      character.css
    src/                # reserved
  data/
    characters/         # character JSON files (runtime, gitignored)
      *.json
```

## Conventions
- Character filename = `character.name + .json` after filename-safe sanitization
- JSON is saved as UTF-8 with indent=2
- LLM features require secrets + config files under `%USERPROFILE%\.ai-trpg\`
- Versioned data goes under `backend/storage/`; `data/` is local-only (gitignored)

## Use on Another Device
1) Install Git and Python 3.13.1
2) `git clone https://github.com/KittyBureau/AI-TRPG.git`
3) `cd AI-TRPG`
4) Create and activate venv:
   - `python -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
5) Install deps: `python -m pip install -r backend/requirements.txt`
6) Configure secrets: `python -m backend.secrets.cli`
7) Run: `python -m uvicorn backend.app.main:app --reload`

Note: `data/` and `backend/data/` are ignored by git. Versioned samples live under `backend/storage/`.
