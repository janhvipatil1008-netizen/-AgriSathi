# ops.ps1 — AgriSathi Operations Menu
# Usage: .\scripts\ops.ps1

$API = "http://localhost:8000"

function Show-Menu {
    Write-Host ""
    Write-Host "===============================" -ForegroundColor Green
    Write-Host "   AgriSathi Operations" -ForegroundColor Green
    Write-Host "===============================" -ForegroundColor Green
    Write-Host " 1. Check system health"
    Write-Host " 2. Trigger all sources now"
    Write-Host " 3. Trigger one source"
    Write-Host " 4. Check Qdrant vector count"
    Write-Host " 5. Test farmer question (English)"
    Write-Host " 6. Test farmer question (Marathi)"
    Write-Host " 7. View recent pipeline logs"
    Write-Host " 8. Restart all containers"
    Write-Host " 9. Exit"
    Write-Host ""
}

function Get-AllSources {
    try {
        $resp = Invoke-RestMethod -Uri "$API/sources" -Method GET -ContentType "application/json"
        return $resp
    } catch {
        Write-Host "ERROR: Could not reach API at $API — is Docker running?" -ForegroundColor Red
        return @()
    }
}

function Invoke-AllSources {
    Write-Host "`nFetching source list..." -ForegroundColor Cyan
    $sources = Get-AllSources
    if ($sources.Count -eq 0) { return }

    $active = $sources | Where-Object { $_.status -eq "active" }
    Write-Host "Triggering $($active.Count) active sources...`n" -ForegroundColor Cyan

    foreach ($src in $active) {
        try {
            Invoke-RestMethod -Uri "$API/sources/$($src.name)/trigger" -Method POST -ContentType "application/json" | Out-Null
            Write-Host "  TRIGGERED  $($src.name)" -ForegroundColor Green
        } catch {
            Write-Host "  FAILED     $($src.name)  — $($_.Exception.Message)" -ForegroundColor Red
        }
        Start-Sleep -Milliseconds 300
    }
    Write-Host "`nDone. Check logs in a few minutes." -ForegroundColor Green
}

function Invoke-OneSource {
    $name = Read-Host "`nEnter source name (e.g. mpkv_cotton_package_of_practices)"
    if ([string]::IsNullOrWhiteSpace($name)) {
        Write-Host "No name entered." -ForegroundColor Yellow
        return
    }
    try {
        $resp = Invoke-RestMethod -Uri "$API/sources/$name/trigger" -Method POST -ContentType "application/json"
        Write-Host "`nTriggered: $name" -ForegroundColor Green
        Write-Host ($resp | ConvertTo-Json -Depth 3)
    } catch {
        Write-Host "`nFailed to trigger '$name': $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Get-QdrantCount {
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:6333/collections/agrisathi_kb" -Method GET
        $count = $resp.result.points_count
        $status = $resp.result.status
        Write-Host "`nQdrant Collection : agrisathi_kb" -ForegroundColor Cyan
        Write-Host "Total vectors     : $count" -ForegroundColor Green
        Write-Host "Status            : $status"
    } catch {
        Write-Host "`nERROR: Could not reach Qdrant — $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Test-EnglishQuestion {
    $body = @{
        question       = "What schemes are available for cotton farmers?"
        farmer_context = @{ crop = "cotton"; district = "Nagpur" }
    } | ConvertTo-Json -Depth 3

    Write-Host "`nAsking (English): What schemes are available for cotton farmers?" -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri "$API/ask" -Method POST -ContentType "application/json" -Body $body
        Write-Host "`nLanguage    : $($resp.language.ToUpper())"
        Write-Host "Chunks used : $($resp.chunks_used)"
        Write-Host "`nAnswer:`n" -ForegroundColor Green
        Write-Host $resp.answer
        if ($resp.sources.Count -gt 0) {
            Write-Host "`nSources: $($resp.sources -join ', ')" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Test-MarathiQuestion {
    $body = @{
        question       = "कापूस पिकावर बोंड अळीचा प्रादुर्भाव झाला आहे काय करावे"
        farmer_context = @{ crop = "cotton"; district = "Nagpur" }
    } | ConvertTo-Json -Depth 3

    Write-Host "`nAsking (Marathi): कापूस पिकावर बोंड अळीचा प्रादुर्भाव झाला आहे काय करावे" -ForegroundColor Cyan
    try {
        $resp = Invoke-RestMethod -Uri "$API/ask" -Method POST -ContentType "application/json" -Body $body
        Write-Host "`nLanguage    : $($resp.language.ToUpper())"
        Write-Host "Chunks used : $($resp.chunks_used)"
        Write-Host "`nAnswer:`n" -ForegroundColor Green
        Write-Host $resp.answer
        if ($resp.sources.Count -gt 0) {
            Write-Host "`nSources: $($resp.sources -join ', ')" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "`nERROR: $($_.Exception.Message)" -ForegroundColor Red
    }
}

function Show-Logs {
    Write-Host "`n--- Last 50 lines from API container ---`n" -ForegroundColor Cyan
    docker logs agrisathi-pipeline-api-1 --tail 50
}

function Restart-Containers {
    Write-Host "`nRestarting all containers..." -ForegroundColor Yellow
    Push-Location "$PSScriptRoot\.."
    docker compose restart
    Pop-Location
    Write-Host "Done. Containers restarted." -ForegroundColor Green
}

# ── Main loop ──────────────────────────────────────────────────────────────────
while ($true) {
    Show-Menu
    $choice = Read-Host "Enter choice (1-9)"

    switch ($choice) {
        "1" { docker exec agrisathi-pipeline-api-1 python scripts/health_check.py }
        "2" { Invoke-AllSources }
        "3" { Invoke-OneSource }
        "4" { Get-QdrantCount }
        "5" { Test-EnglishQuestion }
        "6" { Test-MarathiQuestion }
        "7" { Show-Logs }
        "8" { Restart-Containers }
        "9" { Write-Host "`nGoodbye.`n" -ForegroundColor Green; exit }
        default { Write-Host "`nInvalid choice. Enter 1-9." -ForegroundColor Yellow }
    }

    Write-Host "`nPress Enter to return to menu..." -ForegroundColor DarkGray
    Read-Host | Out-Null
}
