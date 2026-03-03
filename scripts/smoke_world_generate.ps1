param(
    [int]$Port = 18080,
    [switch]$KeepWorkspace
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$workspace = Join-Path $repoRoot ".tmp/smoke_world_generate"
if (Test-Path $workspace) {
    Remove-Item -Recurse -Force $workspace
}
New-Item -ItemType Directory -Path $workspace | Out-Null

$serverProcess = $null
try {
    $serverProcess = Start-Process `
        -FilePath "python" `
        -ArgumentList @(
            "scripts/smoke_world_generate_server.py",
            "--workspace", $workspace,
            "--port", "$Port"
        ) `
        -WorkingDirectory $repoRoot `
        -PassThru

    $baseUrl = "http://127.0.0.1:$Port"
    $health = "$baseUrl/api/v1/openapi.json"
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        try {
            $null = curl.exe -sS $health
            if ($LASTEXITCODE -eq 0) {
                $ready = $true
                break
            }
        } catch {
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $ready) {
        throw "Backend did not become ready: $health"
    }

    function Invoke-JsonPost([string]$Url, [hashtable]$Payload) {
        $body = $Payload | ConvertTo-Json -Depth 20 -Compress
        $tmpBodyPath = [System.IO.Path]::GetTempFileName()
        try {
            $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
            [System.IO.File]::WriteAllText($tmpBodyPath, $body, $utf8NoBom)
            $response = curl.exe -sS -X POST $Url -H "Content-Type: application/json" --data-binary "@$tmpBodyPath"
            if ($LASTEXITCODE -ne 0) {
                throw "curl failed for $Url"
            }
            return ($response | ConvertFrom-Json)
        } finally {
            if (Test-Path $tmpBodyPath) {
                Remove-Item -Force $tmpBodyPath
            }
        }
    }

    function New-CampaignId {
        $resp = Invoke-JsonPost "$baseUrl/api/v1/campaign/create" @{}
        return [string]$resp.campaign_id
    }

    function Read-CampaignJson([string]$CampaignId) {
        $path = Join-Path $workspace "storage/campaigns/$CampaignId/campaign.json"
        $raw = Get-Content -Raw -Encoding UTF8 $path
        return ($raw | ConvertFrom-Json)
    }

    function Write-CampaignJson([string]$CampaignId, $CampaignObj) {
        $path = Join-Path $workspace "storage/campaigns/$CampaignId/campaign.json"
        $json = $CampaignObj | ConvertTo-Json -Depth 30
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($path, $json, $utf8NoBom)
    }

    function Read-WorldJson([string]$WorldId) {
        $path = Join-Path $workspace "storage/worlds/$WorldId/world.json"
        if (-not (Test-Path $path)) {
            throw "world.json not found: $path"
        }
        $raw = Get-Content -Raw -Encoding UTF8 $path
        $obj = $raw | ConvertFrom-Json
        return @{ path = $path; obj = $obj }
    }

    Write-Host "Case A: no world_id and unbound campaign -> world_id_missing"
    $campaignA = New-CampaignId
    $campaignAObj = Read-CampaignJson $campaignA
    $campaignAObj.selected.world_id = ""
    Write-CampaignJson $campaignA $campaignAObj
    $turnA = Invoke-JsonPost "$baseUrl/api/v1/chat/turn" @{
        campaign_id = $campaignA
        user_input = "SMOKE_A"
    }
    if (-not ($turnA.PSObject.Properties.Name -contains "tool_feedback")) {
        $turnAJson = $turnA | ConvertTo-Json -Depth 20
        throw "Case A failed: unexpected response shape: $turnAJson"
    }
    $reasonA = [string]$turnA.tool_feedback.failed_calls[0].reason
    if ($reasonA -ne "world_id_missing") {
        throw "Case A failed: reason=$reasonA"
    }
    Write-Host "  PASS reason=$reasonA"

    Write-Host "Case B: explicit world_id -> create world.json and created=true"
    $campaignB = New-CampaignId
    $turnB = Invoke-JsonPost "$baseUrl/api/v1/chat/turn" @{
        campaign_id = $campaignB
        user_input = "SMOKE_B"
    }
    $resultB = $turnB.applied_actions[0].result
    if (-not $resultB.created) {
        throw "Case B failed: expected created=true"
    }
    $worldB = Read-WorldJson "world_smoke_v1"
    Write-Host ("  PASS world_id={0} created={1} seed={2} generator_id={3}" -f `
            $resultB.world_id, $resultB.created, $resultB.seed, $resultB.generator_id)
    Write-Host ("  world file: {0}" -f $worldB.path)

    Write-Host "Case C: repeat same world_id -> seed/generator stable, updated_at unchanged"
    $beforeSeed = $worldB.obj.seed
    $beforeGenerator = $worldB.obj.generator.id
    $beforeUpdatedAt = $worldB.obj.updated_at
    $turnC = Invoke-JsonPost "$baseUrl/api/v1/chat/turn" @{
        campaign_id = $campaignB
        user_input = "SMOKE_C"
    }
    $resultC = $turnC.applied_actions[0].result
    $worldCAfter = Read-WorldJson "world_smoke_v1"
    if ($resultC.seed -ne $beforeSeed) {
        throw "Case C failed: seed drifted"
    }
    if ([string]$resultC.generator_id -ne [string]$beforeGenerator) {
        throw "Case C failed: generator_id drifted"
    }
    if ([string]$worldCAfter.obj.updated_at -ne [string]$beforeUpdatedAt) {
        throw "Case C failed: updated_at drifted"
    }
    Write-Host ("  PASS seed={0} generator_id={1} updated_at={2}" -f `
            $resultC.seed, $resultC.generator_id, $worldCAfter.obj.updated_at)

    Write-Host "Case D: bind_to_campaign=true then call without world_id succeeds"
    $campaignD = New-CampaignId
    $turnDBind = Invoke-JsonPost "$baseUrl/api/v1/chat/turn" @{
        campaign_id = $campaignD
        user_input = "SMOKE_D_BIND"
    }
    $resultDBind = $turnDBind.applied_actions[0].result
    if (-not $resultDBind.bound_to_campaign) {
        throw "Case D bind failed: bound_to_campaign=false"
    }
    $campaignDObj = Read-CampaignJson $campaignD
    if ([string]$campaignDObj.selected.world_id -ne "world_bound_smoke") {
        throw "Case D bind failed: campaign.selected.world_id not persisted"
    }
    $turnDReuse = Invoke-JsonPost "$baseUrl/api/v1/chat/turn" @{
        campaign_id = $campaignD
        user_input = "SMOKE_D_REUSE"
    }
    $resultDReuse = $turnDReuse.applied_actions[0].result
    if ([string]$resultDReuse.world_id -ne "world_bound_smoke") {
        throw "Case D reuse failed: wrong world_id"
    }
    Write-Host ("  PASS bound_world_id={0} reuse_world_id={1}" -f `
            $campaignDObj.selected.world_id, $resultDReuse.world_id)

    Write-Host ""
    Write-Host "Smoke summary: PASS (A/B/C/D)"
    Write-Host ("Workspace: {0}" -f $workspace)
} finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
    }
    if (-not $KeepWorkspace -and (Test-Path $workspace)) {
        Remove-Item -Recurse -Force $workspace
    }
}
