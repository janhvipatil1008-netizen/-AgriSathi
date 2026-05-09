# AgriSathi Pipeline — Windows PowerShell smoke tests
# Run from any PowerShell terminal on the host machine.
# Requires Docker Compose stack to be running.
#
# Usage:
#   cd "C:\Users\J\OneDrive\Desktop\AgriSathi\Data Downloader\agrisathi-pipeline"
#   .\scripts\test_windows.ps1

$API    = "http://localhost:8000"
$QDRANT = "http://localhost:6333"

function Write-Section($title) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
    Write-Host "  $title" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor DarkCyan
}

# ── 1. Health check ───────────────────────────────────────────────────────────
Write-Section "1. API Health Check"
try {
    $r = Invoke-RestMethod -Uri "$API/health"
    Write-Host "  OK: $($r.status)" -ForegroundColor Green
} catch {
    Write-Host "  FAIL: API not reachable — is Docker running?" -ForegroundColor Red
    exit 1
}

# ── 2. List sources ───────────────────────────────────────────────────────────
Write-Section "2. Registered Sources"
$sources = Invoke-RestMethod -Uri "$API/sources"
foreach ($s in $sources) {
    $hash = if ($s.last_hash) { $s.last_hash.Substring(0,8) + "..." } else { "(none)" }
    Write-Host ("  [{0}] {1,-35} hash={2}" -f $s.status, $s.name, $hash)
}

# ── 3. Trigger each active source ─────────────────────────────────────────────
Write-Section "3. Triggering Active Sources"
$toTrigger = @(
    "mahadbt_scheme_page",
    "agmarknet_market_prices_csv",
    "icar_crop_advisory_pdf",
    "ncipm_pest_alerts"
)
foreach ($name in $toTrigger) {
    try {
        $r = Invoke-RestMethod -Method POST -Uri "$API/sources/$name/trigger"
        Write-Host "  OK  $name — $($r.status)" -ForegroundColor Green
    } catch {
        $code = $_.Exception.Response.StatusCode.value__
        Write-Host "  ERR $name — HTTP $code" -ForegroundColor Yellow
    }
}
Write-Host ""
Write-Host "  (Pipelines run in the background — wait ~60 s before querying)" -ForegroundColor DarkGray

# ── 4. Qdrant collection info ─────────────────────────────────────────────────
Write-Section "4. Qdrant Collection Info"
try {
    $col = Invoke-RestMethod -Uri "$QDRANT/collections/agrisathi_kb"
    $info = $col.result.vectors_count
    $dim  = $col.result.config.params.vectors.size
    Write-Host "  vectors_count : $info"
    Write-Host "  dimension     : $dim"
    if ($dim -ne 1024) {
        Write-Host "  WARN: expected dim=1024 (multilingual-e5-large)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  Collection not found — trigger a source first." -ForegroundColor Yellow
}

# ── 5. Semantic search — English ──────────────────────────────────────────────
Write-Section "5. Semantic Search — English"
$body = @{ text = "farmer scheme eligibility Maharashtra"; top_k = 3 } | ConvertTo-Json
try {
    $hits = Invoke-RestMethod -Method POST -Uri "$API/query" `
        -Body $body -ContentType "application/json"
    if ($hits.Count -eq 0) {
        Write-Host "  No results — embed a source first." -ForegroundColor Yellow
    }
    foreach ($h in $hits) {
        $snippet = $h.text.Substring(0, [Math]::Min(100, $h.text.Length))
        Write-Host ("  score={0:F4} | {1}..." -f $h.score, $snippet)
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# ── 6. Semantic search — Marathi ──────────────────────────────────────────────
Write-Section "6. Semantic Search — Marathi"
$body = @{ text = "शेतकरी योजना अर्ज पात्रता"; top_k = 3 } | ConvertTo-Json -Compress
try {
    $hits = Invoke-RestMethod -Method POST -Uri "$API/query" `
        -Body $body -ContentType "application/json; charset=utf-8"
    if ($hits.Count -eq 0) {
        Write-Host "  No results — embed a source first." -ForegroundColor Yellow
    }
    foreach ($h in $hits) {
        $snippet = $h.text.Substring(0, [Math]::Min(100, $h.text.Length))
        Write-Host ("  score={0:F4} | {1}..." -f $h.score, $snippet)
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

# ── 7. Mandi price search ─────────────────────────────────────────────────────
Write-Section "7. Semantic Search — Mandi Prices"
$body = @{ text = "tomato price Pune quintal"; top_k = 3 } | ConvertTo-Json
try {
    $hits = Invoke-RestMethod -Method POST -Uri "$API/query" `
        -Body $body -ContentType "application/json"
    if ($hits.Count -eq 0) {
        Write-Host "  No mandi results — trigger agmarknet source first." -ForegroundColor Yellow
    }
    foreach ($h in $hits) {
        Write-Host ("  score={0:F4} | {1}" -f $h.score, $h.text)
    }
} catch {
    Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
