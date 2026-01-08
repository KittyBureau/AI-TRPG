# DocumentsAndDirectives

## Quick Start (codes/)
```
cd codes
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
python -m backend.secrets.cli
python -m uvicorn backend.app.main:app --reload
```
Open: `http://127.0.0.1:8000/`

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

## Use on Another Device
1) Install Git and Python 3.13.1
2) `git clone https://github.com/KittyBureau/AI-TRPG.git`
3) `cd AI-TRPG/codes`
4) Create and activate venv:
   - `python -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
5) Install deps: `python -m pip install -r backend/requirements.txt`
6) Configure secrets: `python -m backend.secrets.cli`
7) Run: `python -m uvicorn backend.app.main:app --reload`

Note: `codes/data/` and `codes/backend/data/` are ignored by git. Versioned samples live under `codes/backend/storage/`.
