# Minimal LLM Prototype

## Requirements
- Python 3.13+
- Environment variable `DEEPSEEK_API_KEY` set to your DeepSeek API key

## Install
```
python -m pip install -r backend/requirements.txt
```

## Run
```
python -m uvicorn backend.app.main:app --reload
```

Open `http://127.0.0.1:8000` in your browser.

## Configuration
- Model and base URL are defined in `backend/services/llm_client.py` as constants.
- Optional overrides via `DEEPSEEK_MODEL` and `DEEPSEEK_BASE_URL`.
