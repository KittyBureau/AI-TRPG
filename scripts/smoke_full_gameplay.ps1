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
$totalSteps = 8
$script:LastHttpContext = $null
$script:CurrentStepName = "startup"

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

function Start-Step([int]$Index, [int]$Total, [string]$Name) {
    $script:CurrentStepName = $Name
    $script:LastHttpContext = $null
    Write-Host ""
    Write-Host ("STEP {0}/{1} {2}" -f $Index, $Total, $Name)
}

function Format-JsonForOutput($Value, [int]$MaxLength = 4000) {
    if ($null -eq $Value) {
        return "<null>"
    }
    if ($Value -is [string]) {
        $text = $Value
    } else {
        try {
            $text = $Value | ConvertTo-Json -Depth 30
        } catch {
            $text = [string]$Value
        }
    }
    if ([string]::IsNullOrWhiteSpace($text)) {
        return "<empty>"
    }
    if ($text.Length -le $MaxLength) {
        return $text
    }
    return "{0}`n... <truncated {1} chars>" -f $text.Substring(0, $MaxLength), $text.Length
}

function Write-DiagnosticBlock([string]$Title, [hashtable]$Fields) {
    Write-Host ""
    Write-Host $Title
    foreach ($entry in $Fields.GetEnumerator()) {
        if ($null -eq $entry.Value) {
            continue
        }
        $valueText = [string]$entry.Value
        if ([string]::IsNullOrWhiteSpace($valueText)) {
            continue
        }
        Write-Host ("{0}: {1}" -f $entry.Key, $valueText)
    }
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
    [string]$Message,
    [string]$Expected = "",
    [string]$Actual = "",
    [string]$Method = "",
    [string]$Url = "",
    [string]$StatusCode = "",
    [string]$ResponseBody = "",
    [string]$FailureType = "assertion failure"
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
    if ($FailureType -eq "assertion failure" -and $Step -eq "persistence") {
        $FailureType = "file/persistence failure"
    }
    Write-DiagnosticBlock -Title "[FAIL] $Step" -Fields ([ordered]@{
        step = $Step
        failure_type = $FailureType
        field = $Field
        location = $location
        method = $Method
        url = $Url
        status_code = $StatusCode
        expected = $Expected
        actual = $Actual
        response_body = $ResponseBody
        message = $Message
    })
    throw ("[{0}] {1}: {2}" -f $FailureType, $Step, $Message)
}

function Assert-True(
    [bool]$Condition,
    [string]$Step,
    [string]$Field,
    [string]$FilePath,
    [string]$Pattern,
    [string]$Message,
    [string]$Expected = "",
    [string]$Actual = ""
) {
    if (-not $Condition) {
        $httpContext = $script:LastHttpContext
        $effectiveExpected = if ([string]::IsNullOrWhiteSpace($Expected)) { "condition should be true" } else { $Expected }
        $effectiveActual = if ([string]::IsNullOrWhiteSpace($Actual)) { "condition evaluated to false" } else { $Actual }
        Fail-Step `
            -Step $Step `
            -Field $Field `
            -FilePath $FilePath `
            -Pattern $Pattern `
            -Message $Message `
            -Expected $effectiveExpected `
            -Actual $effectiveActual `
            -Method ([string]$httpContext.method) `
            -Url ([string]$httpContext.url) `
            -StatusCode ([string]$httpContext.status_code) `
            -ResponseBody (Format-JsonForOutput $httpContext.body_text) `
            -FailureType "assertion failure"
    }
}

function Invoke-JsonPost([string]$Step, [string]$Url, [hashtable]$Payload) {
    $body = $Payload | ConvertTo-Json -Depth 30 -Compress
    $tmpBodyPath = [System.IO.Path]::GetTempFileName()
    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($tmpBodyPath, $body, $utf8NoBom)
        $response = curl.exe -sS -X POST $Url -H "Content-Type: application/json" --data-binary "@$tmpBodyPath" -w "`n__STATUS_CODE__:%{http_code}"
        if ($response -is [System.Array]) {
            $response = $response -join "`n"
        }
        if ($LASTEXITCODE -ne 0) {
            Fail-Step `
                -Step $Step `
                -Field "http" `
                -FilePath "" `
                -Pattern "" `
                -Message "curl failed" `
                -Expected "successful HTTP request" `
                -Actual ("curl exit code {0}" -f $LASTEXITCODE) `
                -Method "POST" `
                -Url $Url `
                -ResponseBody "<curl produced no response body>" `
                -FailureType "HTTP error"
        }

        $statusMarker = "__STATUS_CODE__:"
        $statusIndex = $response.LastIndexOf($statusMarker)
        $bodyText = if ($statusIndex -ge 0) { $response.Substring(0, $statusIndex).TrimEnd() } else { $response }
        $statusText = if ($statusIndex -ge 0) { $response.Substring($statusIndex + $statusMarker.Length).Trim() } else { "" }
        $statusCode = 0
        [void][int]::TryParse($statusText, [ref]$statusCode)

        $context = [pscustomobject]@{
            method = "POST"
            url = $Url
            status_code = $statusCode
            body_text = $bodyText
            json = $null
        }
        $script:LastHttpContext = $context

        if ($statusCode -lt 200 -or $statusCode -ge 300) {
            Fail-Step `
                -Step $Step `
                -Field "http.status" `
                -FilePath "" `
                -Pattern "" `
                -Message "Non-success HTTP status" `
                -Expected "2xx" `
                -Actual ([string]$statusCode) `
                -Method $context.method `
                -Url $context.url `
                -StatusCode ([string]$context.status_code) `
                -ResponseBody (Format-JsonForOutput $context.body_text) `
                -FailureType "HTTP error"
        }

        try {
            $context.json = if ([string]::IsNullOrWhiteSpace($bodyText)) { $null } else { $bodyText | ConvertFrom-Json }
        } catch {
            Fail-Step `
                -Step $Step `
                -Field "response body" `
                -FilePath "" `
                -Pattern "" `
                -Message "Response body is not valid JSON" `
                -Expected "valid JSON body" `
                -Actual "JSON parse error" `
                -Method $context.method `
                -Url $context.url `
                -StatusCode ([string]$context.status_code) `
                -ResponseBody (Format-JsonForOutput $context.body_text) `
                -FailureType "JSON parse error"
        }

        return $context
    } finally {
        if (Test-Path $tmpBodyPath) {
            Remove-Item -Force $tmpBodyPath
        }
    }
}

function Invoke-Turn([string]$Step, [string]$BaseUrl, [string]$CampaignId, [string]$Token) {
    return Invoke-JsonPost $Step "$BaseUrl/api/v1/chat/turn" @{
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

    Start-Step 1 $totalSteps "create_campaign"
    $createRespEnvelope = Invoke-JsonPost "create_campaign" "$baseUrl/api/v1/campaign/create" @{}
    $createResp = $createRespEnvelope.json
    $campaignId = [string]$createResp.campaign_id
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace($campaignId)) `
        "create_campaign" `
        "response.campaign_id" `
        "" `
        "" `
        "campaign_id is empty" `
        "non-empty campaign_id" `
        $campaignId
    $campaignPath = Join-Path $workspace "storage/campaigns/$campaignId/campaign.json"
    Add-StepResult "create_campaign" "PASS" ("campaign_id={0}" -f $campaignId)

    Start-Step 2 $totalSteps "world_generate"
    $turnWorld = (Invoke-Turn "world_generate" $baseUrl $campaignId "SMOKE_FULL_WORLD").json
    $worldActions = @($turnWorld.applied_actions)
    Assert-True `
        ($worldActions.Count -ge 1) `
        "world_generate" `
        "applied_actions[0]" `
        $campaignPath `
        "selected" `
        "applied_actions is empty" `
        "at least one applied action" `
        ($worldActions.Count)
    Assert-True `
        ([string]$worldActions[0].tool -eq "world_generate") `
        "world_generate" `
        "applied_actions[0].tool" `
        $campaignPath `
        "world_id" `
        ("unexpected tool: {0}" -f [string]$worldActions[0].tool) `
        "world_generate" `
        ([string]$worldActions[0].tool)
    $worldResult = $worldActions[0].result
    $worldId = [string]$worldResult.world_id
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace($worldId)) `
        "world_generate" `
        "result.world_id" `
        $campaignPath `
        "world_id" `
        "result.world_id is empty" `
        "non-empty world_id" `
        $worldId
    Assert-True `
        ([bool]$worldResult.bound_to_campaign) `
        "world_generate" `
        "result.bound_to_campaign" `
        $campaignPath `
        "world_id" `
        "expected bound_to_campaign=true" `
        "true" `
        ([string]$worldResult.bound_to_campaign)
    $worldPath = Join-Path $workspace "storage/worlds/$worldId/world.json"
    Assert-True `
        (Test-Path $worldPath) `
        "world_generate" `
        "storage.worlds.<world_id>.world.json" `
        $worldPath `
        "world_id" `
        "world.json does not exist" `
        "existing world.json file" `
        $worldPath
    Add-StepResult "world_generate" "PASS" ("world_id={0}" -f $worldId)

    Start-Step 3 $totalSteps "map_generate"
    $turnMap = (Invoke-Turn "map_generate" $baseUrl $campaignId "SMOKE_FULL_MAP").json
    $mapActions = @($turnMap.applied_actions)
    Assert-True `
        ($mapActions.Count -ge 1) `
        "map_generate" `
        "applied_actions[0]" `
        $campaignPath `
        "map" `
        "applied_actions is empty" `
        "at least one applied action" `
        ($mapActions.Count)
    Assert-True `
        ([string]$mapActions[0].tool -eq "map_generate") `
        "map_generate" `
        "applied_actions[0].tool" `
        $campaignPath `
        "map" `
        ("unexpected tool: {0}" -f [string]$mapActions[0].tool) `
        "map_generate" `
        ([string]$mapActions[0].tool)
    $createdAreaIds = @($mapActions[0].result.created_area_ids)
    Assert-True `
        ($createdAreaIds.Count -ge 1) `
        "map_generate" `
        "result.created_area_ids" `
        $campaignPath `
        "areas" `
        "created_area_ids is empty" `
        "at least one created area" `
        ($createdAreaIds.Count)
    Add-StepResult "map_generate" "PASS" ("created_area_ids={0}" -f ($createdAreaIds -join ","))

    Start-Step 4 $totalSteps "actor_spawn"
    $turnSpawn = (Invoke-Turn "actor_spawn" $baseUrl $campaignId "SMOKE_FULL_SPAWN").json
    $spawnActions = @($turnSpawn.applied_actions)
    Assert-True `
        ($spawnActions.Count -ge 1) `
        "actor_spawn" `
        "applied_actions[0]" `
        $campaignPath `
        "actors" `
        "applied_actions is empty" `
        "at least one applied action" `
        ($spawnActions.Count)
    Assert-True `
        ([string]$spawnActions[0].tool -eq "actor_spawn") `
        "actor_spawn" `
        "applied_actions[0].tool" `
        $campaignPath `
        "actors" `
        ("unexpected tool: {0}" -f [string]$spawnActions[0].tool) `
        "actor_spawn" `
        ([string]$spawnActions[0].tool)
    $spawnResult = $spawnActions[0].result
    $spawnedActorId = [string]$spawnResult.actor_id
    Assert-True `
        ($spawnedActorId.StartsWith("actor_")) `
        "actor_spawn" `
        "result.actor_id" `
        $campaignPath `
        "actor_" `
        ("unexpected actor_id: {0}" -f $spawnedActorId) `
        "actor_*" `
        $spawnedActorId
    Add-StepResult "actor_spawn" "PASS" ("actor_id={0}" -f $spawnedActorId)

    Start-Step 5 $totalSteps "move_options"
    $turnOptions = (Invoke-Turn "move_options" $baseUrl $campaignId "SMOKE_FULL_OPTIONS").json
    $optionActions = @($turnOptions.applied_actions)
    Assert-True `
        ($optionActions.Count -ge 1) `
        "move_options" `
        "applied_actions[0]" `
        $campaignPath `
        "map" `
        "applied_actions is empty" `
        "at least one applied action" `
        ($optionActions.Count)
    Assert-True `
        ([string]$optionActions[0].tool -eq "move_options") `
        "move_options" `
        "applied_actions[0].tool" `
        $campaignPath `
        "reachable_area_ids" `
        ("unexpected tool: {0}" -f [string]$optionActions[0].tool) `
        "move_options" `
        ([string]$optionActions[0].tool)
    $options = @($optionActions[0].result.options)
    Assert-True `
        ($options.Count -ge 1) `
        "move_options" `
        "result.options" `
        $campaignPath `
        "reachable_area_ids" `
        "options is empty" `
        "at least one move option" `
        ($options.Count)
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
        "area_002 not found in options" `
        "option containing area_002" `
        (Format-JsonForOutput $options)
    Add-StepResult "move_options" "PASS" ("options={0}" -f ($options.Count))

    Start-Step 6 $totalSteps "move"
    $turnMove = (Invoke-Turn "move" $baseUrl $campaignId "SMOKE_FULL_MOVE").json
    $moveActions = @($turnMove.applied_actions)
    Assert-True `
        ($moveActions.Count -ge 1) `
        "move" `
        "applied_actions[0]" `
        $campaignPath `
        "position" `
        "applied_actions is empty" `
        "at least one applied action" `
        ($moveActions.Count)
    Assert-True `
        ([string]$moveActions[0].tool -eq "move") `
        "move" `
        "applied_actions[0].tool" `
        $campaignPath `
        "position" `
        ("unexpected tool: {0}" -f [string]$moveActions[0].tool) `
        "move" `
        ([string]$moveActions[0].tool)
    Assert-True `
        ([string]$moveActions[0].result.to_area_id -eq "area_002") `
        "move" `
        "result.to_area_id" `
        $campaignPath `
        "area_002" `
        ("unexpected to_area_id: {0}" -f [string]$moveActions[0].result.to_area_id) `
        "area_002" `
        ([string]$moveActions[0].result.to_area_id)
    Add-StepResult "move" "PASS" "pc_001 moved to area_002"

    Start-Step 7 $totalSteps "chat_turn"
    $turnChat = (Invoke-Turn "chat_turn" $baseUrl $campaignId "SMOKE_FULL_CHAT").json
    $chatActions = @($turnChat.applied_actions)
    Assert-True `
        ($chatActions.Count -eq 0) `
        "chat_turn" `
        "applied_actions" `
        $campaignPath `
        "turn_log" `
        "expected no tool application in final chat turn" `
        "0 applied actions" `
        ($chatActions.Count)
    $narrativeText = [string]$turnChat.narrative_text
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace($narrativeText)) `
        "chat_turn" `
        "narrative_text" `
        $campaignPath `
        "turn_log" `
        "narrative_text is empty" `
        "non-empty narrative_text" `
        $narrativeText
    Add-StepResult "chat_turn" "PASS" "non-tool narrative turn completed"

    Start-Step 8 $totalSteps "persistence"
    Assert-True `
        (Test-Path $campaignPath) `
        "persistence" `
        "campaign.json" `
        $campaignPath `
        "\"id\"" `
        "campaign.json missing" `
        "existing campaign.json file" `
        $campaignPath
    $campaignObj = Get-Content -Raw -Encoding UTF8 $campaignPath | ConvertFrom-Json

    Assert-True `
        ([string]$campaignObj.selected.world_id -eq $worldId) `
        "persistence" `
        "selected.world_id" `
        $campaignPath `
        "\"world_id\"" `
        ("selected.world_id mismatch: {0}" -f [string]$campaignObj.selected.world_id) `
        $worldId `
        ([string]$campaignObj.selected.world_id)

    foreach ($areaId in $createdAreaIds) {
        $hasArea = $campaignObj.map.areas.PSObject.Properties.Name -contains [string]$areaId
        Assert-True `
            $hasArea `
            "persistence" `
            ("map.areas.{0}" -f [string]$areaId) `
            $campaignPath `
            [string]$areaId `
            ("missing generated area: {0}" -f [string]$areaId) `
            [string]$areaId `
            (Format-JsonForOutput $campaignObj.map.areas.PSObject.Properties.Name)
    }

    $hasSpawnedActor = $campaignObj.actors.PSObject.Properties.Name -contains $spawnedActorId
    Assert-True `
        $hasSpawnedActor `
        "persistence" `
        "actors.<spawned_actor_id>" `
        $campaignPath `
        $spawnedActorId `
        ("spawned actor not persisted: {0}" -f $spawnedActorId) `
        $spawnedActorId `
        (Format-JsonForOutput $campaignObj.actors.PSObject.Properties.Name)
    $spawnedActor = $campaignObj.actors.PSObject.Properties[$spawnedActorId].Value
    Assert-True `
        ([string]$spawnedActor.meta.character_id -eq "char_smoke_support") `
        "persistence" `
        "actors.<spawned_actor_id>.meta.character_id" `
        $campaignPath `
        "\"character_id\"" `
        ("unexpected character_id: {0}" -f [string]$spawnedActor.meta.character_id) `
        "char_smoke_support" `
        ([string]$spawnedActor.meta.character_id)
    $partyIds = @($campaignObj.selected.party_character_ids)
    Assert-True `
        ($partyIds -contains $spawnedActorId) `
        "persistence" `
        "selected.party_character_ids" `
        $campaignPath `
        "\"party_character_ids\"" `
        "spawned actor not bound to party" `
        $spawnedActorId `
        (Format-JsonForOutput $partyIds)
    Assert-True `
        ([string]$campaignObj.actors.pc_001.position -eq "area_002") `
        "persistence" `
        "actors.pc_001.position" `
        $campaignPath `
        "\"position\"" `
        ("pc_001 position mismatch: {0}" -f [string]$campaignObj.actors.pc_001.position) `
        "area_002" `
        ([string]$campaignObj.actors.pc_001.position)

    Assert-True `
        (Test-Path $worldPath) `
        "persistence" `
        "world.json" `
        $worldPath `
        "\"world_id\"" `
        "world.json missing" `
        "existing world.json file" `
        $worldPath
    $worldObj = Get-Content -Raw -Encoding UTF8 $worldPath | ConvertFrom-Json
    Assert-True `
        ([string]$worldObj.world_id -eq $worldId) `
        "persistence" `
        "world.world_id" `
        $worldPath `
        "\"world_id\"" `
        ("world_id mismatch: {0}" -f [string]$worldObj.world_id) `
        $worldId `
        ([string]$worldObj.world_id)
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace([string]$worldObj.seed)) `
        "persistence" `
        "world.seed" `
        $worldPath `
        "\"seed\"" `
        "world.seed empty" `
        "non-empty world.seed" `
        ([string]$worldObj.seed)
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace([string]$worldObj.generator.id)) `
        "persistence" `
        "world.generator.id" `
        $worldPath `
        "\"generator\"" `
        "world.generator.id empty" `
        "non-empty world.generator.id" `
        ([string]$worldObj.generator.id)

    $turnLogPath = Join-Path $workspace "storage/campaigns/$campaignId/turn_log.jsonl"
    Assert-True `
        (Test-Path $turnLogPath) `
        "persistence" `
        "turn_log.jsonl" `
        $turnLogPath `
        "turn_id" `
        "turn_log.jsonl missing" `
        "existing turn_log.jsonl file" `
        $turnLogPath
    $turnRows = Get-Content -Path $turnLogPath -Encoding UTF8 | Where-Object { $_.Trim() -ne "" }
    Assert-True `
        ($turnRows.Count -ge 6) `
        "persistence" `
        "turn_log row count" `
        $turnLogPath `
        "turn_id" `
        ("expected >=6 turns, actual={0}" -f $turnRows.Count) `
        ">= 6 turns" `
        ([string]$turnRows.Count)
    $lastTurn = $turnRows[-1] | ConvertFrom-Json
    Assert-True `
        ([string]$lastTurn.user_input -eq "SMOKE_FULL_CHAT") `
        "persistence" `
        "turn_log.last.user_input" `
        $turnLogPath `
        "SMOKE_FULL_CHAT" `
        ("unexpected last user_input: {0}" -f [string]$lastTurn.user_input) `
        "SMOKE_FULL_CHAT" `
        ([string]$lastTurn.user_input)
    Assert-True `
        (-not [string]::IsNullOrWhiteSpace([string]$lastTurn.assistant_text)) `
        "persistence" `
        "turn_log.last.assistant_text" `
        $turnLogPath `
        "assistant_text" `
        "last assistant_text is empty" `
        "non-empty assistant_text" `
        ([string]$lastTurn.assistant_text)
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
    Add-StepResult $script:CurrentStepName "FAIL" $_.Exception.Message
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
        $removed = $false
        for ($attempt = 1; $attempt -le 5 -and -not $removed; $attempt++) {
            try {
                Remove-Item -Recurse -Force -ErrorAction Stop $workspace
                $removed = $true
            } catch {
                if ($attempt -lt 5) {
                    Start-Sleep -Milliseconds 250
                } else {
                    Write-Warning ("Workspace cleanup skipped: {0}" -f $_.Exception.Message)
                }
            }
        }
    }
}
