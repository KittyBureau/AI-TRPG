# Docs Path Mapping (2026-03-05)

## Purpose

This document records the one-time docs reorganization mapping so changes are reversible.

## Immutable Zones

These paths were intentionally not moved:

- `docs/_index/**`
- `docs/_archive/**`
- `docs/99_human_only/**`

## Old -> New Mapping

| Old path | New path | Migration reason | Compatibility note |
| --- | --- | --- | --- |
| `docs/02_guides/gameplay_flow.md` | `docs/20_runtime/gameplay_flow.md` | Runtime flow docs grouped under `20_runtime`. | Old path kept as migration note. |
| `docs/02_guides/api_v1_route_migration.md` | `docs/20_runtime/api_v1_route_migration.md` | Runtime API route note grouped with runtime docs. | Old path kept as migration note. |
| `docs/02_guides/testing/api_test_guide.md` | `docs/20_runtime/testing/api_test_guide.md` | Single authoritative API testing guide under runtime/testing. | Old path kept as migration note. |
| `docs/02_guides/testing/active_actor_integration_smoke.md` | `docs/20_runtime/testing/active_actor_integration_smoke.md` | Keep all smoke docs under one runtime testing tree. | Old path kept as migration note. |
| `docs/02_guides/testing/full_gameplay_smoke_test.md` | `docs/20_runtime/testing/full_gameplay_smoke_test.md` | Keep all smoke docs under one runtime testing tree. | Old path kept as migration note. |
| `docs/02_guides/testing/map_generate_manual_test.md` | `docs/20_runtime/testing/map_generate_manual_test.md` | Keep all smoke docs under one runtime testing tree. | Old path kept as migration note. |
| `docs/02_guides/testing/state_consistency_check.md` | `docs/20_runtime/testing/state_consistency_check.md` | Keep all smoke docs under one runtime testing tree. | Old path kept as migration note. |
| `docs/02_guides/testing/world_generate_smoke_test.md` | `docs/20_runtime/testing/world_generate_smoke_test.md` | Keep all smoke docs under one runtime testing tree. | Old path kept as migration note. |
| `docs/03_architecture/external_resources_todo.md` | `docs/30_resources/external_resources_and_trace.md` | Resource/trace contracts consolidated under resource docs. | Old path kept as migration note. |
| `docs/reviews/capability_inventory.md` | `docs/10_architecture/capability_inventory.md` | Architecture inventory grouped under architecture docs. | No stub required. |
| `docs/test/API_TEST_GUIDE.md` | `docs/20_runtime/testing/api_test_guide.md` (authority) | Remove parallel API guide authority conflict. | File retained as migration redirect. |

## Rollback Procedure

1. Verify scope: `git status --short`
2. Revert all docs reorg changes: `git restore README.md docs resources/CHANGELOG.md`
3. If rollback should keep unrelated edits: restore selected files from this mapping table only.
4. Validate old paths: `rg --files docs/02_guides docs/03_architecture docs/test`
5. Re-run link/path check (below) to confirm baseline.

## One-time Broken Link / Path Check

Run from repo root in PowerShell:

```powershell
$files = @('README.md') + (Get-ChildItem docs -Recurse -File -Include *.md | ForEach-Object { $_.FullName })
$pattern = '(?<![A-Za-z0-9_./-])(docs|frontend|resources|scripts)/[A-Za-z0-9_./-]+'
$broken = @()
foreach ($file in $files) {
  $text = Get-Content -Raw -LiteralPath $file
  foreach ($m in [regex]::Matches($text, $pattern)) {
    $candidate = $m.Value.TrimEnd('.', ',', ')', ']', '"', "'")
    if (-not (Test-Path -LiteralPath $candidate) -and -not (Test-Path -LiteralPath (Join-Path (Split-Path -Parent $file) $candidate))) {
      $broken += [pscustomobject]@{ file = $file; path = $candidate }
    }
  }
}
$broken | Sort-Object file, path -Unique | Format-Table -AutoSize
```

Expected result after this refresh: no broken paths in entry docs (`README.md`, `docs/00_overview/README.md`, `docs/_index/AI_INDEX.md`).
