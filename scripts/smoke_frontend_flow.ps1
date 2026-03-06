param(
    [int]$Port = 18082,
    [string]$RunId = "",
    [int]$RetryAttempts = 2,
    [switch]$KeepWorkspace
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfff")
}
$RetryAttempts = [Math]::Min(5, [Math]::Max(1, $RetryAttempts))

$workspace = Join-Path $repoRoot ".tmp/smoke_frontend_flow/$RunId"
if (Test-Path $workspace) {
    Remove-Item -Recurse -Force $workspace
}
New-Item -ItemType Directory -Path $workspace | Out-Null

$serverProcess = $null
$testPassed = $false
$stepResults = New-Object System.Collections.Generic.List[object]

function Add-StepResult([string]$Step, [string]$Status, [string]$Detail) {
    $stepResults.Add(
        [pscustomobject]@{
            step = $Step
            status = $Status
            detail = $Detail
        }
    ) | Out-Null
    Write-Host ("[{0}] {1} - {2}" -f $Status, $Step, $Detail)
}

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) {
        throw $Message
    }
}

function Invoke-JsonPost([string]$Url, [hashtable]$Payload) {
    $body = $Payload | ConvertTo-Json -Depth 50 -Compress
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

function Build-FlowInstruction([string]$Tool, [hashtable]$ToolArgs) {
    $argsJson = $ToolArgs | ConvertTo-Json -Depth 20 -Compress
    return (
        "[UI_FLOW_STEP] Return JSON with keys assistant_text, dialog_type, tool_calls. " +
        "Execute exactly one tool_call now: $Tool. " +
        "Use args exactly: $argsJson. " +
        "Do not call any additional tools. " +
        "Keep assistant_text empty."
    )
}

function Invoke-ToolStep(
    [string]$BaseUrl,
    [string]$CampaignId,
    [string]$StepName,
    [string]$ExpectedTool,
    [hashtable]$ToolArgs
) {
    for ($attempt = 1; $attempt -le $RetryAttempts; $attempt++) {
        $instruction = Build-FlowInstruction -Tool $ExpectedTool -ToolArgs $ToolArgs
        $turn = Invoke-JsonPost "$BaseUrl/api/v1/chat/turn" @{
            campaign_id = $CampaignId
            user_input = $instruction
        }
        $actions = @($turn.applied_actions)
        if ($actions.Count -ge 1 -and [string]$actions[0].tool -eq $ExpectedTool) {
            Add-StepResult $StepName "PASS" ("tool={0}, attempt={1}" -f $ExpectedTool, $attempt)
            return @{
                ok = $true
                turn = $turn
                attempt = $attempt
            }
        }
    }
    Add-StepResult $StepName "FAIL" ("tool={0} not applied after {1} attempts" -f $ExpectedTool, $RetryAttempts)
    return @{
        ok = $false
        turn = $null
        attempt = $RetryAttempts
    }
}

Write-Host ("Run command: powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1")
Write-Host ("Run command (keep workspace): powershell -ExecutionPolicy Bypass -File scripts/smoke_frontend_flow.ps1 -KeepWorkspace")
Write-Host ("Workspace: {0}" -f $workspace)

try {
    $serverProcess = Start-Process `
        -FilePath "python" `
        -ArgumentList @(
            "scripts/smoke_frontend_flow_server.py",
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
    Assert-True $ready "Backend did not become ready: $health"

    $createResp = Invoke-JsonPost "$baseUrl/api/v1/campaign/create" @{}
    $campaignId = [string]$createResp.campaign_id
    Assert-True (-not [string]::IsNullOrWhiteSpace($campaignId)) "create_campaign failed: empty campaign_id"
    Add-StepResult "create_campaign" "PASS" ("campaign_id={0}" -f $campaignId)

    $worldStep = Invoke-ToolStep $baseUrl $campaignId "world_generate" "world_generate" @{
        world_id = "world_ui_flow_v1"
        bind_to_campaign = $true
    }
    Assert-True $worldStep.ok "world_generate did not apply expected tool"

    $mapStep = Invoke-ToolStep $baseUrl $campaignId "map_generate" "map_generate" @{
        parent_area_id = "area_001"
        theme = "UI Path"
        constraints = @{
            size = 3
            seed = "ui-flow"
        }
    }
    Assert-True $mapStep.ok "map_generate did not apply expected tool"

    $spawnStep = Invoke-ToolStep $baseUrl $campaignId "actor_spawn" "actor_spawn" @{
        character_id = "char_ui_support"
        bind_to_party = $true
    }
    Assert-True $spawnStep.ok "actor_spawn did not apply expected tool"
    $spawnedActorId = [string]$spawnStep.turn.applied_actions[0].result.actor_id
    Assert-True (-not [string]::IsNullOrWhiteSpace($spawnedActorId)) "actor_spawn returned empty actor_id"

    $setActive = Invoke-JsonPost "$baseUrl/api/v1/campaign/select_actor" @{
        campaign_id = $campaignId
        active_actor_id = $spawnedActorId
    }
    Assert-True ([string]$setActive.active_actor_id -eq $spawnedActorId) "select_actor did not return requested active actor"
    Add-StepResult "select_actor" "PASS" ("active_actor_id={0}" -f $spawnedActorId)

    $campaignGet = curl.exe -sS "$baseUrl/api/v1/campaign/get?campaign_id=$campaignId" | ConvertFrom-Json
    Assert-True ([string]$campaignGet.selected.active_actor_id -eq $spawnedActorId) "campaign/get active_actor_id mismatch"
    Assert-True (@($campaignGet.selected.party_character_ids) -contains $spawnedActorId) "campaign/get party missing spawned actor"
    Add-StepResult "refresh_campaign" "PASS" ("active={0}, party={1}" -f [string]$campaignGet.selected.active_actor_id, @($campaignGet.selected.party_character_ids).Count)

    $moveStep = Invoke-ToolStep $baseUrl $campaignId "move" "move" @{
        actor_id = $spawnedActorId
        to_area_id = "area_002"
    }
    Assert-True $moveStep.ok "move did not apply expected tool"

    $turn = Invoke-JsonPost "$baseUrl/api/v1/chat/turn" @{
        campaign_id = $campaignId
        user_input = "Describe the current scene without calling tools."
        execution = @{
            actor_id = $spawnedActorId
        }
    }
    Assert-True ($turn.PSObject.Properties.Name -contains "narrative_text") "chat_turn missing narrative_text"
    Assert-True ($turn.PSObject.Properties.Name -contains "state_summary") "chat_turn missing state_summary"
    Assert-True ([string]$turn.effective_actor_id -eq $spawnedActorId) "chat_turn effective_actor_id mismatch"
    $chatActions = @($turn.applied_actions)
    Assert-True ($chatActions.Count -eq 0) "chat_turn expected no applied_actions"
    Add-StepResult "chat_turn" "PASS" "narrative-only turn shape validated"

    $testPassed = $true
    Write-Host ""
    Write-Host "Smoke summary:"
    foreach ($result in $stepResults) {
        Write-Host (" - {0}: {1}" -f $result.step, $result.status)
    }
    Write-Host ("Result: PASS ({0}/{1})" -f @($stepResults | Where-Object { $_.status -eq "PASS" }).Count, $stepResults.Count)
    Write-Host ("Workspace: {0}" -f $workspace)
} catch {
    Add-StepResult "frontend_flow" "FAIL" $_.Exception.Message
    Write-Host ""
    Write-Host "Smoke summary:"
    foreach ($result in $stepResults) {
        Write-Host (" - {0}: {1}" -f $result.step, $result.status)
    }
    Write-Host ("Result: FAIL ({0}/{1})" -f @($stepResults | Where-Object { $_.status -eq "PASS" }).Count, $stepResults.Count)
    Write-Host ("Workspace: {0}" -f $workspace)
    throw
} finally {
    if ($serverProcess -and -not $serverProcess.HasExited) {
        Stop-Process -Id $serverProcess.Id -Force
    }
    if ($testPassed -and -not $KeepWorkspace -and (Test-Path $workspace)) {
        Remove-Item -Recurse -Force $workspace
    }
}
