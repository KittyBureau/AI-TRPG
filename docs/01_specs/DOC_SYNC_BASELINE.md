# DOC Sync Baseline

## Purpose

Keep the lightweight Google Drive reference-doc package usable for the web project after each milestone.

## Current Mechanism

- Script: `scripts/sync_chatgpt_docs.ps1`
- Wrapper: `scripts/sync_chatgpt_docs.bat`
- Target: `gdrive:AI-TRPG_docs`
- Model: explicit include list in the script, not full-directory mirroring

## Milestone Rule

After each milestone or meaningful docs change:

1. Update the relevant docs first.
2. Check whether a new high-value doc must be added to the sync script include list.
3. Update `scripts/sync_chatgpt_docs.ps1` only if the include list must change.
4. Run the sync once.

## Must-Sync Categories

- project overview and current status
- architecture and spec-alignment docs
- current playable/runtime docs
- current milestone design/reference docs
- current smoke or entrypoint docs when they matter to web-side alignment

## Do Not Sync

- code directories
- storage/runtime data
- broad repo mirroring
- temporary or low-value docs unless clearly needed

## Expected Outcome

New milestone docs are not available to the web project until the include list is updated if needed and the sync is run.
