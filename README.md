# DocumentsAndDirectives

## Quick Start (codes/)
```
cd codes
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:DEEPSEEK_API_KEY="YOUR_KEY"
python -m uvicorn backend.app.main:app --reload
```
Open: `http://127.0.0.1:8000/`

## Use on Another Device
1) Install Git and Python 3.13.1
2) `git clone https://github.com/KittyBureau/AI-TRPG.git`
3) `cd AI-TRPG/codes`
4) Create and activate venv:
   - `python -m venv .venv`
   - `.\.venv\Scripts\Activate.ps1`
5) Install deps: `python -m pip install -r backend/requirements.txt`
6) Set API key: `$env:DEEPSEEK_API_KEY="YOUR_KEY"`
7) Run: `python -m uvicorn backend.app.main:app --reload`

Note: `codes/data/` is ignored by git. Copy `codes/data/characters/` manually if needed.
