# Raw Request Console (Frontend)

This is a static, framework-free UI for sending raw JSON requests to the FastAPI backend.

## Run (static)

1. Start the backend (default: `http://127.0.0.1:8000`).
2. Serve this folder with any static server.

Example using Python:

```bash
cd frontend
python -m http.server 5173
```

Then open `http://127.0.0.1:5173` and set **Base URL** to `http://127.0.0.1:8000`.

Notes:
- CORS is enabled for `http://localhost:*` and `http://127.0.0.1:*` in `backend/api/main.py`.
- Opening the HTML directly via `file://` is not recommended; use a static server.

## What it does

- Sends raw JSON exactly as typed (no validation).
- Displays response fields + raw response.
- Records each request/response in local history with export/copy tools.
