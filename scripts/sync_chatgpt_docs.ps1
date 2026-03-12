$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$DriveRoot = "gdrive:AI-TRPG_docs"
$ProxyUrl = "http://127.0.0.1:7897"

$env:HTTP_PROXY = $ProxyUrl
$env:HTTPS_PROXY = $ProxyUrl

function Get-RclonePath {
    if ($env:RCLONE_EXE -and (Test-Path -LiteralPath $env:RCLONE_EXE)) {
        return (Resolve-Path -LiteralPath $env:RCLONE_EXE).Path
    }

    $command = Get-Command rclone -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(
        "C:\tools\rclone\rclone.exe",
        "C:\Program Files\rclone\rclone.exe",
        "C:\Program Files (x86)\rclone\rclone.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    throw "rclone.exe was not found. Set RCLONE_EXE, add rclone to PATH, or install it in a supported fallback location."
}

function Invoke-Rclone {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $stdoutFile = [System.IO.Path]::GetTempFileName()
    $stderrFile = [System.IO.Path]::GetTempFileName()

    try {
        $process = Start-Process -FilePath $script:RclonePath `
            -ArgumentList $Arguments `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutFile `
            -RedirectStandardError $stderrFile

        $stdout = if (Test-Path -LiteralPath $stdoutFile) {
            Get-Content -LiteralPath $stdoutFile
        } else {
            @()
        }
        $stderr = if (Test-Path -LiteralPath $stderrFile) {
            Get-Content -LiteralPath $stderrFile
        } else {
            @()
        }
    } finally {
        Remove-Item -LiteralPath $stdoutFile -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderrFile -ErrorAction SilentlyContinue
    }

    $output = @($stdout) + @($stderr)
    $exitCode = if ($null -ne $process) { $process.ExitCode } else { $LASTEXITCODE }

    if ($exitCode -ne 0) {
        if ($output.Count -gt 0) {
            $output | ForEach-Object { Write-Host $_ }
        }
        throw "rclone exited with code $exitCode."
    }

    return $output
}

function Test-NeedsUpload {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LocalPath,
        [Parameter(Mandatory = $true)]
        [string]$RemoteDirectory
    )

    $leafName = Split-Path -Path $LocalPath -Leaf
    $dryRunOutput = Invoke-Rclone -Arguments @("copy", "--dry-run", "--stats", "0", $LocalPath, $RemoteDirectory)

    foreach ($line in $dryRunOutput) {
        if ($line -match [regex]::Escape($leafName)) {
            return $true
        }
    }

    return $false
}

$script:RclonePath = Get-RclonePath

$FileMappings = @(
    [pscustomobject]@{ RelativePath = "README.md" },
    [pscustomobject]@{ RelativePath = "docs/_index/AI_INDEX.md" },
    [pscustomobject]@{ RelativePath = "docs/00_overview/README.md" },
    [pscustomobject]@{ RelativePath = "docs/00_overview/PROJECT_STATUS.md" },
    [pscustomobject]@{ RelativePath = "docs/00_overview/DOCS_PATH_MAPPING.md" },
    [pscustomobject]@{ RelativePath = "docs/01_specs/architecture.md" },
    [pscustomobject]@{ RelativePath = "docs/01_specs/DOC_SYNC_BASELINE.md" },
    [pscustomobject]@{ RelativePath = "docs/01_specs/TODO_DOCS_ALIGNMENT.md" },
    [pscustomobject]@{ RelativePath = "docs/20_runtime/storage_authority.md" },
    [pscustomobject]@{ RelativePath = "docs/20_runtime/frontend_entrypoints.md" },
    [pscustomobject]@{ RelativePath = "docs/20_runtime/testing/scenario_world_panel_smoke.md" },
    [pscustomobject]@{ RelativePath = "docs/90_playable/PLAYABLE_V1_TODO.md" },
    [pscustomobject]@{ RelativePath = "docs/90_playable/P2_PLAYABLE_SCENARIO_GENERATOR_V0.md" },
    [pscustomobject]@{ RelativePath = "docs/90_playable/P2_RUNTIME_CONTEXT_DEVELOPER_REFERENCE.md" },
    [pscustomobject]@{ RelativePath = "docs/90_playable/P2_RUNTIME_CONTEXT_ARCHITECTURE_OVERVIEW.md" },
    [pscustomobject]@{ RelativePath = "docs/90_playable/P2_CONTEXT_BUILDER_IMPLEMENTATION_PREP.md" }
)

Write-Host "Repo root: $RepoRoot"
Write-Host "Using rclone: $script:RclonePath"
Write-Host "Drive root: $DriveRoot"
Write-Host "HTTP_PROXY: $env:HTTP_PROXY"
Write-Host "HTTPS_PROXY: $env:HTTPS_PROXY"

Invoke-Rclone -Arguments @("mkdir", $DriveRoot) | Out-Null

$uploadedCount = 0
$skippedCount = 0

foreach ($mapping in $FileMappings) {
    $relativePath = $mapping.RelativePath
    $localPath = Join-Path $RepoRoot ($relativePath -replace "/", "\")
    if (-not (Test-Path -LiteralPath $localPath)) {
        throw "Missing source file: $relativePath"
    }

    $remoteDirectory = Split-Path -Path "$DriveRoot/$relativePath" -Parent

    Write-Host "Considering $relativePath"

    if (Test-NeedsUpload -LocalPath $localPath -RemoteDirectory $remoteDirectory) {
        Invoke-Rclone -Arguments @("copy", "--stats", "0", $localPath, $remoteDirectory) | Out-Null
        Write-Host "Result: uploaded"
        $uploadedCount++
    } else {
        Write-Host "Result: skipped (unchanged)"
        $skippedCount++
    }
}

Write-Host "ChatGPT docs sync completed. Uploaded: $uploadedCount. Skipped: $skippedCount."
