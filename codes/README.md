# codes directory overview

This folder hosts the minimal runnable prototype: FastAPI backend, static frontend, and on-disk character data.

## Quick entrypoints
- Backend entry: `backend/app/main.py` (compat entry: `backend/main.py`)
- Frontend entry: `frontend/public/index.html`
- Character tool page: `/character`
- Character data directory: `data/characters/`

## Run (PowerShell)
```
.\.venv\Scripts\Activate.ps1
$env:DEEPSEEK_API_KEY="YOUR_KEY"
python -m uvicorn backend.app.main:app --reload
```
Open: `http://127.0.0.1:8000/`

## Key modules
- `backend/services/llm_client.py`: /turn uses DeepSeek with strict JSON validation + retry
- `backend/services/character_service.py`: character generation, rename, and save (DeepSeek JSON + comment)
- `frontend/public/app.js`: index chat logic
- `frontend/public/character.js`: character tool UI logic

## Current structure
```text
codes/
  .venv/                # local virtual environment
  backend/
    app/                # app entry
      main.py
    services/           # business services
      llm_client.py
      character_service.py
    api/                # reserved
    agents/             # reserved
    core/               # reserved
    tools/              # reserved
    storage/            # reserved
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
    characters/         # character JSON files
      *.json
```

## Conventions
- Character filename = `character.name + .json` after filename-safe sanitization
- JSON is saved as UTF-8 with indent=2
- `DEEPSEEK_API_KEY` must be set for LLM-backed features
