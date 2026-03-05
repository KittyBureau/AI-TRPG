# Resources Changelog

This changelog tracks versioned External Resources updates and rollback notes.

## Entry Template

- Date: `YYYY-MM-DD`
- Summary: short description
- Affected resources:
  - `<kind>/<name>@<version>` `hash=<sha256>`
- Rollback:
  - how to revert manifest `enabled` selection and/or restore previous file

## 2026-03-05

- Summary: Added manifest hash fields for governance and static consistency testing.
- Affected resources:
  - `prompts/turn_profile_default@v1` `hash=fa04d5f5faa162b23a0fa1ed74fc8f74263b87dfb199e069cb5898f69e6fddaa`
  - `flows/play_turn_basic@v1` `hash=125e59ccf2f8ca71bcfc5e0feb51194ec51fdfbacb4a031010a3712a4299c757`
  - `schemas/debug_resources_v1@v1` `hash=80b29b551676686afab8887765901a27c21ed9a9044040cc7f239975bfba5818`
  - `templates/campaign_stub@v1` `hash=252e7bb587fbd18d6fb41ed882330210aa266a65a0e0ea17d9320423848cc10c`
- Rollback:
  - Revert `resources/manifest.json` to the previous commit and run `pytest -q`.
