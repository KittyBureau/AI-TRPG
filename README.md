# AI-TRPG

Minimal backend + frontend prototype for AI-assisted TRPG flow.

## Version

- Project version: `1.0`

## Quick Start (Local)

Commands below assume you are running from the repository root.

Important:

- Backend storage/config paths resolve from the current working directory as `storage/...`.
- Use the repo root as the working directory for backend commands.
- `python scripts/run_backend.py` enforces the repo-root path automatically.

### Requirements

- Python `3.10+`
- Node is **not** required for the current frontend. It is plain static HTML/JS.

### Install Dependencies

```bash
python -m venv .venv
pip install -r requirements.txt
```

### Choose One Local Path

#### A. Smoke Mode (no LLM credentials required)

Use this first if you only want to verify the repo works locally.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1
```

Related deterministic smoke scripts:

- `scripts/smoke_world_generate.ps1`
- `scripts/smoke_full_gameplay.ps1`
- `scripts/smoke_frontend_flow.ps1`

These scripts patch in a local smoke LLM and run against temporary workspace storage.

#### B. Real Local Run (LLM-backed)

1. Initialize the local config/keyring entry for the active profile:

```bash
python -m backend.tools.setup_keyring
```

This will:

- copy `storage/config/llm_config.example.json` to `storage/config/llm_config.json` if needed
- prompt for the API key and keyring passphrase
- create or populate `storage/secrets/keyring.json` for the active `api_key_ref`

2. Review `storage/config/llm_config.json` if you need a different model, base URL, or profile.

### Run Backend

Preferred local launcher:

```bash
python scripts/run_backend.py
```

Optional host/port overrides:

- `AI_TRPG_HOST`
- `AI_TRPG_PORT`
- `AI_TRPG_RELOAD`

Default backend URL:

- `http://127.0.0.1:8000`

If runtime status reports `passphrase_required`, unlock the existing keyring for the running server:

```bash
python -m backend.tools.unlock_keyring
```

### Optional Frontend

Serve the static frontend from the repo root:

```bash
cd frontend
python -m http.server 5173
```

Then open:

- `http://127.0.0.1:5173/play.html`
- `http://127.0.0.1:5173/debug.html`

Use backend base URL:

- `http://127.0.0.1:8000`

### Minimal Validation

The smallest no-credential verification path is:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/smoke_world_generate.ps1
```

If you are doing a real local run, a quick manual check is:

- start backend with `python scripts/run_backend.py`
- open `http://127.0.0.1:8000/api/v1/docs`
- check `GET /api/v1/runtime/status`

## Documentation Entry

- Main docs index: `docs/00_overview/README.md`
- AI task index: `docs/_index/AI_INDEX.md`

## Documentation Workflow

- Primary workflow: local VSCode + Codex with the full repository as source of truth.
- ChatGPT web project context uses a lightweight Google Drive reference-doc package refreshed via `scripts/sync_chatgpt_docs.ps1`.
- That package is intentionally small and stage-oriented; detailed implementation lookup should still happen from the local repo, usually through Codex.
- Current item-system/runtime truth is stack-first: portable item authority is `campaign.items`, frontend inventory authority derives from stack payloads, and `selected_stack_id` is the normal selection/submit path.

## Current Runtime Truth

- Core portable-item loop is `search -> reveal -> take`.
- `campaign.items` is the authoritative portable-item store.
- `actors[*].inventory` is a derived compatibility view only.
- `search` does not grant possession; actor ownership changes on `take`.
- Gate checks still use `required_item_id` rules, but possession evidence comes from actor-owned stacks derived from `campaign.items`.
- `inventory_add` still exists as a bounded legacy-only contract for source-entity-backed inventory gain; it is not the mainline gameplay path.
- Formal Gameplay Model is currently a read-only structural validation and alignment layer:
  - `dependency_groups` with `all_of` / `any_of`
  - `multi_path_coverage` and `clue_support_coverage`
  - gate/overall quality, authoring audit, preset alignment audit, and remediation backlog output
- The formal layer is non-authoritative and does not affect runtime, turn execution, or tool execution.

## Current Item Docs

- Runtime truth: `docs/20_runtime/item_runtime_model.md`
- Persistence truth: `docs/20_runtime/storage_authority.md`
- Tool contract details: `docs/01_specs/tools.md`
