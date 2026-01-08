# Architecture

## Overview
- Runtime code lives under `codes/` (FastAPI backend + static frontend).
- Design/spec docs live under `docs/`.

## Current layering
- API layer: `codes/backend/app/main.py` (FastAPI routes and request models).
- Service layer: `codes/backend/services/`
  - `llm_client.py` (LLM call + JSON validation)
  - `character_service.py` (character generation/save)
  - `world_movement.py` (movement paths + apply move)
- Storage (JSON files): `codes/backend/storage/`
  - `worlds/` (static world graph)
  - `runs/` (dynamic state + facts)
- Runtime data outputs: `codes/data/characters/` (gitignored).
- Frontend: `codes/frontend/public/` (static HTML/JS/CSS).
- Tests: `codes/backend/tests/` (placeholder; runner 待确认, default: pytest).

## Boundaries
- API layer should be thin; delegate to services and translate errors to JSON responses.
- Services should avoid importing FastAPI and return plain data or raise domain errors.
- Storage access is via services; frontend does not read storage directly.
- Gitignored data directories are local-only and not part of versioned fixtures.

## External dependencies
- FastAPI + Pydantic for HTTP layer.
- httpx for LLM calls.

## Open items (待确认)
- Storage abstraction (JSON vs DB) and locking strategy.
- Test runner and CI workflow.
