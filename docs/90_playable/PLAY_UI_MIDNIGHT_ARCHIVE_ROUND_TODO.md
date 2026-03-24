# Play UI + Midnight Archive Round TODO

Last updated: 2026-03-24

Legend:
- `TODO`: not started
- `WIP`: in progress
- `DONE`: completed and verified

## Block 1. Round Setup
- Status: `DONE`
- Goal: isolate this round from previously completed Midnight Archive preset/doc work.
- Verification:
  - prior work committed separately before new edits
  - this file exists and is updated as blocks move

## Block 2. Scenario / Runtime Fixes
- Status: `DONE`
- Scope:
  - Midnight Archive must not auto-complete on entering `restricted_archive`
  - completion must require explicit final interaction in the final area
  - service route must require `routing_slip`
  - preserve official route and watchtower behavior
- Target files:
  - `backend/app/world_presets.py`
  - `backend/app/tool_executor.py`
  - `backend/tests/test_midnight_archive_world.py`
  - related targeted backend tests only if needed
- Verification:
  - entering `restricted_archive` alone leaves goal active
  - interacting with final payoff object completes the scenario
  - `returns_annex -> restricted_archive` fails without `routing_slip`
  - official route still works
  - no deadlock when `clerk_office` is skipped
  - watchtower targeted tests still pass

## Block 3. Controlled Pickup Backend Support
- Status: `DONE`
- Scope:
  - additive turn request support for selected world item/object pickup target
  - validate selected pickup target is visible, reachable, and takeable now
  - reject invalid selection truthfully
  - keep existing free-text compatibility path intact
- Target files:
  - `backend/api/routes/chat.py`
  - `backend/app/turn_service.py`
  - `backend/app/tool_executor.py`
  - targeted backend tests for request contract and validation
- Verification:
  - selected pickup target is accepted only when valid in current area
  - stale or remote target is rejected
  - existing turns without the new hint still work

## Block 4. User-Facing Play UI Foundation
- Status: `DONE`
- Scope:
  - keep `debug.html` as-is
  - upgrade `play.html` / `play.js` / play panels into a basic player-facing screen
  - clearly show narrative, area, NPCs, interactive objects, takeable items, selected target, and latest result
  - allow controlled pickup selection from visible scene items
  - show immediate move feedback without reading raw JSON
- Target files:
  - `frontend/play.html`
  - `frontend/play.js`
  - `frontend/styles.css`
  - `frontend/store/store.js`
  - `frontend/panels/*.js`
  - focused frontend tests
- Verification:
  - play page is usable without reading debug JSON
  - debug page still loads separately
  - move result and current narrative are visible after each turn
  - visible NPCs / objects / takeable items are surfaced clearly
  - selected pickup target is shown and sent

## Block 5. Deferred Design-Only Notes
- Status: `DONE`
- Keep deferred in this round:
  - per-NPC memory for non-preset conversation
  - general fact persistence for generated conversation outcomes
  - free action / attack / mistake budget / recoverable failure systems
- Verification:
  - documented briefly only
  - no runtime implementation added
