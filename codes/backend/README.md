# Minimal LLM Prototype

## Requirements
- Python 3.13+
- Local encrypted secrets file + config JSON under `%USERPROFILE%\.ai-trpg\`

## Install
```
python -m pip install -r backend/requirements.txt
```

## Run
```
python -m uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

## Docs
- `docs/ai/AI_INDEX.md`
- `docs/ai/CONVENTIONS.md`

## Services
- `backend/services/llm_client.py` (LLM call + JSON validation)
- `backend/services/character_service.py` (character generation + save)
- `backend/services/world_movement.py` (movement paths + apply move)

## Configuration
- Configure routing and provider settings in `%USERPROFILE%\.ai-trpg\config.json`.
- Store API keys in `%USERPROFILE%\.ai-trpg\secrets.enc` via `python -m backend.secrets.cli`.
- `config.json` supports `routing.all` as a default provider for all features.
