param(
    [int]$Port = 18081,
    [string]$RunId = "",
    [switch]$KeepWorkspace
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfff")
}

$workspace = Join-Path $repoRoot ".tmp/smoke_full_gameplay/$RunId"
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

function Get-FieldLine([string]$FilePath, [string]$Pattern) {
    if ([string]::IsNullOrWhiteSpace($FilePath)) {
        return 0
    }
    if (-not (Test-Path $FilePath)) {
        return 0
    }
    $lines = Get-Content -Path $FilePath -Encoding UTF8
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -like "*$Pattern*") {
            return ($i + 1)
        }
    }
    return 1
}

function Fail-Step(
    [string]$Step,
    [string]$Field,
    [string]$FilePath,
    [string]$Pattern,
    [string]$Message
) {
    $line = Get-FieldLine -FilePath $FilePath -Pattern $Pattern
    $location = "N/A"
    if (-not [string]::IsNullOrWhiteSpace($FilePath)) {
        if ($line -gt 0) {
            $location = "$FilePath`:$line"
        } else {
            $location = $FilePath
        }
    }
    throw ("定位: {0} -> {1} -> {2} | {3}" -f $Step, $Field, $location, $Message)
}

function Assert-True(
    [bool]$Condition,
    [string]$Step,
    [string]$Field,
    [string]$FilePath,
    [string]$Pattern,
    [string]$Message
) {
    if (-not $Condition) {
        Fail-Step -Step $Step -Field $Field -FilePath $FilePath -Pattern $Pattern -Message $Message
    }
}

function Invoke-JsonPost([string]$Url, [hashtable]$Payload) {
    $body = $Payload | ConvertTo-Json -Depth 30 -Compress
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

function Invoke-Turn([string]$BaseUrl, [string]$CampaignId, [string]$Token) {
    return Invoke-JsonPost "$BaseUrl/api/v1/chat/turn" @{
        campaign_id = $CampaignId
        user_input = $Token
    }
}

Write-Host ("Run command: powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1")
Write-Host ("Run command (keep workspace): powershell -ExecutionPolicy Bypass -File scripts/smoke_full_gameplay.ps1 -KeepWorkspace")
Write-Host ("Workspace: {0}" -f $workspace)

try {
    $serverProcess = Start-Process `
        -FilePath "python" `
        -ArgumentList @(
            "scripts/smoke_full_gameplay_server.py",
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

    $createResp = Invoke-JsonPost "$baseUrl/api/v1/campaign/create" @{}
    $campaignId = [string]$createResp.campaign_id
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace($campaignId)) `
        "create_campaign" `
        "response.campaign_id" `
        "" `
        "" `
        "campaign_id is empty"
    $campaignPath = Join-Path $workspace "storage/campaigns/$campaignId/campaign.json"
    Add-StepResult "create_campaign" "PASS" ("campaign_id={0}" -f $campaignId)

    $turnWorld = Invoke-Turn $baseUrl $campaignId "SMOKE_FULL_WORLD"
    $worldActions = @($turnWorld.applied_actions)
    Assert-True `
        ($worldActions.Count -ge 1) `
        "world_generate" `
        "applied_actions[0]" `
        $campaignPath `
        "selected" `
        "applied_actions is empty"
    Assert-True `
        ([string]$worldActions[0].tool -eq "world_generate") `
        "world_generate" `
        "applied_actions[0].tool" `
        $campaignPath `
        "world_id" `
        ("unexpected tool: {0}" -f [string]$worldActions[0].tool)
    $worldResult = $worldActions[0].result
    $worldId = [string]$worldResult.world_id
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace($worldId)) `
        "world_generate" `
        "result.world_id" `
        $campaignPath `
        "world_id" `
        "result.world_id is empty"
    Assert-True `
        ([bool]$worldResult.bound_to_campaign) `
        "world_generate" `
        "result.bound_to_campaign" `
        $campaignPath `
        "world_id" `
        "expected bound_to_campaign=true"
    $worldPath = Join-Path $workspace "storage/worlds/$worldId/world.json"
    Assert-True `
        (Test-Path $worldPath) `
        "world_generate" `
        "storage.worlds.<world_id>.world.json" `
        $worldPath `
        "world_id" `
        "world.json does not exist"
    Add-StepResult "world_generate" "PASS" ("world_id={0}" -f $worldId)

    $turnMap = Invoke-Turn $baseUrl $campaignId "SMOKE_FULL_MAP"
    $mapActions = @($turnMap.applied_actions)
    Assert-True `
        ($mapActions.Count -ge 1) `
        "map_generate" `
        "applied_actions[0]" `
        $campaignPath `
        "map" `
        "applied_actions is empty"
    Assert-True `
        ([string]$mapActions[0].tool -eq "map_generate") `
        "map_generate" `
        "applied_actions[0].tool" `
        $campaignPath `
        "map" `
        ("unexpected tool: {0}" -f [string]$mapActions[0].tool)
    $createdAreaIds = @($mapActions[0].result.created_area_ids)
    Assert-True `
        ($createdAreaIds.Count -ge 1) `
        "map_generate" `
        "result.created_area_ids" `
        $campaignPath `
        "areas" `
        "created_area_ids is empty"
    Add-StepResult "map_generate" "PASS" ("created_area_ids={0}" -f ($createdAreaIds -join ","))

    $turnSpawn = Invoke-Turn $baseUrl $campaignId "SMOKE_FULL_SPAWN"
    $spawnActions = @($turnSpawn.applied_actions)
    Assert-True `
        ($spawnActions.Count -ge 1) `
        "actor_spawn" `
        "applied_actions[0]" `
        $campaignPath `
        "actors" `
        "applied_actions is empty"
    Assert-True `
        ([string]$spawnActions[0].tool -eq "actor_spawn") `
        "actor_spawn" `
        "applied_actions[0].tool" `
        $campaignPath `
        "actors" `
        ("unexpected tool: {0}" -f [string]$spawnActions[0].tool)
    $spawnResult = $spawnActions[0].result
    $spawnedActorId = [string]$spawnResult.actor_id
    Assert-True `
        ($spawnedActorId.StartsWith("actor_")) `
        "actor_spawn" `
        "result.actor_id" `
        $campaignPath `
        "actor_" `
        ("unexpected actor_id: {0}" -f $spawnedActorId)
    Add-StepResult "actor_spawn" "PASS" ("actor_id={0}" -f $spawnedActorId)

    $turnOptions = Invoke-Turn $baseUrl $campaignId "SMOKE_FULL_OPTIONS"
    $optionActions = @($turnOptions.applied_actions)
    Assert-True `
        ($optionActions.Count -ge 1) `
        "move_options" `
        "applied_actions[0]" `
        $campaignPath `
        "map" `
        "applied_actions is empty"
    Assert-True `
        ([string]$optionActions[0].tool -eq "move_options") `
        "move_options" `
        "applied_actions[0].tool" `
        $campaignPath `
        "reachable_area_ids" `
        ("unexpected tool: {0}" -f [string]$optionActions[0].tool)
    $options = @($optionActions[0].result.options)
    Assert-True `
        ($options.Count -ge 1) `
        "move_options" `
        "result.options" `
        $campaignPath `
        "reachable_area_ids" `
        "options is empty"
    $hasArea002 = $false
    foreach ($item in $options) {
        if ([string]$item.to_area_id -eq "area_002") {
            $hasArea002 = $true
            break
        }
    }
    Assert-True `
        $hasArea002 `
        "move_options" `
        "result.options[*].to_area_id" `
        $campaignPath `
        "area_002" `
        "area_002 not found in options"
    Add-StepResult "move_options" "PASS" ("options={0}" -f ($options.Count))

    $turnMove = Invoke-Turn $baseUrl $campaignId "SMOKE_FULL_MOVE"
    $moveActions = @($turnMove.applied_actions)
    Assert-True `
        ($moveActions.Count -ge 1) `
        "move" `
        "applied_actions[0]" `
        $campaignPath `
        "position" `
        "applied_actions is empty"
    Assert-True `
        ([string]$moveActions[0].tool -eq "move") `
        "move" `
        "applied_actions[0].tool" `
        $campaignPath `
        "position" `
        ("unexpected tool: {0}" -f [string]$moveActions[0].tool)
    Assert-True `
        ([string]$moveActions[0].result.to_area_id -eq "area_002") `
        "move" `
        "result.to_area_id" `
        $campaignPath `
        "area_002" `
        ("unexpected to_area_id: {0}" -f [string]$moveActions[0].result.to_area_id)
    Add-StepResult "move" "PASS" "pc_001 moved to area_002"

    $turnChat = Invoke-Turn $baseUrl $campaignId "SMOKE_FULL_CHAT"
    $chatActions = @($turnChat.applied_actions)
    Assert-True `
        ($chatActions.Count -eq 0) `
        "chat_turn" `
        "applied_actions" `
        $campaignPath `
        "turn_log" `
        "expected no tool application in final chat turn"
    $narrativeText = [string]$turnChat.narrative_text
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace($narrativeText)) `
        "chat_turn" `
        "narrative_text" `
        $campaignPath `
        "turn_log" `
        "narrative_text is empty"
    Add-StepResult "chat_turn" "PASS" "non-tool narrative turn completed"

    Assert-True `
        (Test-Path $campaignPath) `
        "persistence" `
        "campaign.json" `
        $campaignPath `
        "\"id\"" `
        "campaign.json missing"
    $campaignObj = Get-Content -Raw -Encoding UTF8 $campaignPath | ConvertFrom-Json

    Assert-True `
        ([string]$campaignObj.selected.world_id -eq $worldId) `
        "persistence" `
        "selected.world_id" `
        $campaignPath `
        "\"world_id\"" `
        ("selected.world_id mismatch: {0}" -f [string]$campaignObj.selected.world_id)

    foreach ($areaId in $createdAreaIds) {
        $hasArea = $campaignObj.map.areas.PSObject.Properties.Name -contains [string]$areaId
        Assert-True `
            $hasArea `
            "persistence" `
            ("map.areas.{0}" -f [string]$areaId) `
            $campaignPath `
            [string]$areaId `
            ("missing generated area: {0}" -f [string]$areaId)
    }

    $hasSpawnedActor = $campaignObj.actors.PSObject.Properties.Name -contains $spawnedActorId
    Assert-True `
        $hasSpawnedActor `
        "persistence" `
        "actors.<spawned_actor_id>" `
        $campaignPath `
        $spawnedActorId `
        ("spawned actor not persisted: {0}" -f $spawnedActorId)
    $spawnedActor = $campaignObj.actors.PSObject.Properties[$spawnedActorId].Value
    Assert-True `
        ([string]$spawnedActor.meta.character_id -eq "char_smoke_support") `
        "persistence" `
        "actors.<spawned_actor_id>.meta.character_id" `
        $campaignPath `
        "\"character_id\"" `
        ("unexpected character_id: {0}" -f [string]$spawnedActor.meta.character_id)
    $partyIds = @($campaignObj.selected.party_character_ids)
    Assert-True `
        ($partyIds -contains $spawnedActorId) `
        "persistence" `
        "selected.party_character_ids" `
        $campaignPath `
        "\"party_character_ids\"" `
        "spawned actor not bound to party"
    Assert-True `
        ([string]$campaignObj.actors.pc_001.position -eq "area_002") `
        "persistence" `
        "actors.pc_001.position" `
        $campaignPath `
        "\"position\"" `
        ("pc_001 position mismatch: {0}" -f [string]$campaignObj.actors.pc_001.position)

    Assert-True `
        (Test-Path $worldPath) `
        "persistence" `
        "world.json" `
        $worldPath `
        "\"world_id\"" `
        "world.json missing"
    $worldObj = Get-Content -Raw -Encoding UTF8 $worldPath | ConvertFrom-Json
    Assert-True `
        ([string]$worldObj.world_id -eq $worldId) `
        "persistence" `
        "world.world_id" `
        $worldPath `
        "\"world_id\"" `
        ("world_id mismatch: {0}" -f [string]$worldObj.world_id)
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace([string]$worldObj.seed)) `
        "persistence" `
        "world.seed" `
        $worldPath `
        "\"seed\"" `
        "world.seed empty"
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace([string]$worldObj.generator.id)) `
        "persistence" `
        "world.generator.id" `
        $worldPath `
        "\"generator\"" `
        "world.generator.id empty"

    $turnLogPath = Join-Path $workspace "storage/campaigns/$campaignId/turn_log.jsonl"
    Assert-True `
        (Test-Path $turnLogPath) `
        "persistence" `
        "turn_log.jsonl" `
        $turnLogPath `
        "turn_id" `
        "turn_log.jsonl missing"
    $turnRows = Get-Content -Path $turnLogPath -Encoding UTF8 | Where-Object { $_.Trim() -ne "" }
    Assert-True `
        ($turnRows.Count -ge 6) `
        "persistence" `
        "turn_log row count" `
        $turnLogPath `
        "turn_id" `
        ("expected >=6 turns, actual={0}" -f $turnRows.Count)
    $lastTurn = $turnRows[-1] | ConvertFrom-Json
    Assert-True `
        ([string]$lastTurn.user_input -eq "SMOKE_FULL_CHAT") `
        "persistence" `
        "turn_log.last.user_input" `
        $turnLogPath `
        "SMOKE_FULL_CHAT" `
        ("unexpected last user_input: {0}" -f [string]$lastTurn.user_input)
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace([string]$lastTurn.assistant_text)) `
        "persistence" `
        "turn_log.last.assistant_text" `
        $turnLogPath `
        "assistant_text" `
        "last assistant_text is empty"
    Add-StepResult "persistence" "PASS" ("campaign/world/turn_log validated for {0}" -f $campaignId)

    $testPassed = $true
    Write-Host ""
    Write-Host "Smoke summary:"
    foreach ($result in $stepResults) {
        Write-Host (" - {0}: {1}" -f $result.step, $result.status)
    }
    Write-Host ("Result: PASS ({0}/{1})" -f @($stepResults | Where-Object { $_.status -eq "PASS" }).Count, $stepResults.Count)
    Write-Host ("Workspace: {0}" -f $workspace)
} catch {
    Add-StepResult "full_gameplay_loop" "FAIL" $_.Exception.Message
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
