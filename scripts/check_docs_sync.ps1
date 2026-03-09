param(
    [string]$DiffRange = "HEAD~1..HEAD",
    [string[]]$ChangedFiles,
    [string]$CommitMessage = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Get-ChangedFiles {
    param(
        [string]$Range,
        [string[]]$ExplicitFiles
    )

    if ($null -ne $ExplicitFiles -and $ExplicitFiles.Count -gt 0) {
        return $ExplicitFiles
    }

    $output = & git diff --name-only $Range 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error ("FAIL docs_sync_git_diff_error: {0}" -f ($output -join [Environment]::NewLine))
        exit 1
    }
    if ($output -is [System.Array]) {
        return @($output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }
    if ([string]::IsNullOrWhiteSpace([string]$output)) {
        return @()
    }
    return @([string]$output)
}

function Get-CommitMessageText {
    param([string]$ExplicitMessage)

    if (-not [string]::IsNullOrWhiteSpace($ExplicitMessage)) {
        return $ExplicitMessage
    }

    $output = & git log -1 --pretty=%B 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error ("FAIL docs_sync_git_log_error: {0}" -f ($output -join [Environment]::NewLine))
        exit 1
    }
    if ($output -is [System.Array]) {
        return ($output -join [Environment]::NewLine)
    }
    return [string]$output
}

$files = @(Get-ChangedFiles -Range $DiffRange -ExplicitFiles $ChangedFiles)
$commitText = Get-CommitMessageText -ExplicitMessage $CommitMessage

$backendChanges = @($files | Where-Object { $_ -like "backend/*" })
$frontendChanges = @($files | Where-Object { $_ -like "frontend/*" })
$docsChanges = @($files | Where-Object { $_ -like "docs/*" })
$todoChanged = $files -contains "docs/90_playable/PLAYABLE_V1_TODO.md"
$aiIndexChanged = $files -contains "docs/_index/AI_INDEX.md"
$criticalBackendChanges = @(
    $files | Where-Object {
        $_ -like "backend/app/*" -or
        $_ -like "backend/domain/*" -or
        $_ -like "backend/api/*"
    }
)

if (($backendChanges.Count -gt 0 -or $frontendChanges.Count -gt 0) -and $docsChanges.Count -eq 0) {
    Write-Error "FAIL docs_sync_missing"
    exit 1
}

if ($criticalBackendChanges.Count -gt 0 -and -not $aiIndexChanged) {
    Write-Error "FAIL ai_index_not_updated"
    exit 1
}

if ($todoChanged -and $commitText -notmatch "P1-") {
    Write-Error "FAIL todo_state_change_without_task_reference"
    exit 1
}

Write-Output "[PASS] docs sync check"
