# AgriSathi Pipeline — Windows verification script
# Run from any PowerShell terminal on the host machine.
# Requires Docker Compose stack to be running.
#
# Usage:
#   cd "C:\Users\J\OneDrive\Desktop\AgriSathi\Data Downloader\agrisathi-pipeline"
#   .\scripts\verify_windows.ps1

$API       = "http://localhost:8000"
$QDRANT    = "http://localhost:6333"
$CONTAINER = "agrisathi-pipeline-api-1"

function Write-Section($title) {
    Write-Host ""
    Write-Host ("─" * 60) -ForegroundColor DarkCyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host ("─" * 60) -ForegroundColor DarkCyan
}

# ── a. Run verify_pipeline.py inside the container ────────────────────────────
Write-Section "a. Running end-to-end pipeline verification"
Write-Host "  (This downloads, extracts, embeds and queries Qdrant.)"
Write-Host "  First run loads the model — may take several minutes."
Write-Host ""
docker exec $CONTAINER python scripts/verify_pipeline.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  FAIL: verify_pipeline.py exited with code $LASTEXITCODE" -ForegroundColor Red
} else {
    Write-Host ""
    Write-Host "  verify_pipeline.py completed successfully." -ForegroundColor Green
}

# ── b. Qdrant collection point count ─────────────────────────────────────────
Write-Section "b. Qdrant collection info"
try {
    $col = Invoke-RestMethod -Uri "$QDRANT/collections/agrisathi_kb"
    $pts = $col.result.vectors_count
    $dim = $col.result.config.params.vectors.size
    Write-Host "  vectors_count : $pts"
    Write-Host "  dimension     : $dim  (expected 1024 for multilingual-e5-large)"
    if ($pts -eq 0) {
        Write-Host "  WARN: 0 vectors — pipeline may not have completed yet." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  Collection not found — run the pipeline first." -ForegroundColor Yellow
}

# ── c. POST /ask — English question ──────────────────────────────────────────
Write-Section "c. POST /ask — cotton pest management (English)"
$body = @{
    question       = "cotton pest management"
    farmer_context = @{
        crop     = "cotton"
        district = "Nagpur"
    }
} | ConvertTo-Json -Depth 3

try {
    $resp = Invoke-RestMethod -Method POST -Uri "$API/ask" `
        -ContentType "application/json" -Body $body
    Write-Host "  language    : $($resp.language)"
    Write-Host "  chunks_used : $($resp.chunks_used)"
    Write-Host "  sources     : $($resp.sources -join ', ')"
    Write-Host ""
    Write-Host "  Answer (first 300 chars):"
    Write-Host "  $($resp.answer.Substring(0, [Math]::Min(300, $resp.answer.Length))) …"
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# ── d. POST /ask — Marathi question ──────────────────────────────────────────
Write-Section "d. POST /ask — Marathi question"
$bodyMr = @{
    question       = "कापूस पिकावर कीड नियंत्रण कसे करावे?"
    farmer_context = @{
        crop     = "cotton"
        district = "Nagpur"
    }
} | ConvertTo-Json -Depth 3 -Compress

try {
    $resp = Invoke-RestMethod -Method POST -Uri "$API/ask" `
        -ContentType "application/json; charset=utf-8" -Body $bodyMr
    Write-Host "  language    : $($resp.language)"
    Write-Host "  chunks_used : $($resp.chunks_used)"
    Write-Host ""
    Write-Host "  Answer (first 300 chars):"
    Write-Host "  $($resp.answer.Substring(0, [Math]::Min(300, $resp.answer.Length))) …"
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host ("─" * 60) -ForegroundColor DarkGray
Write-Host "  Done." -ForegroundColor Green
