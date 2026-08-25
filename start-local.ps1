# Pornește Argus Custode local: backend (FastAPI) + frontend (build servit static).
#
# Rulează-l dintr-un terminal normal, nu dintr-o sesiune de agent: procesele pornite de
# un agent sunt oprite când se încheie sesiunea lui.
#
#   .\start-local.ps1
#
# Deschide apoi http://127.0.0.1:4173
# Oprire: Ctrl+C în această fereastră (oprește și fereastra backendului).

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\python.exe'
$frontend = Join-Path $root 'app\frontend'
$backendPort = 8077
$frontendPort = 4173

if (-not (Test-Path $python)) {
    Write-Error "Nu găsesc mediul virtual la $python. Creează-l întâi: python -m venv .venv"
}

Write-Host "1/3  Pornesc backendul pe portul $backendPort..." -ForegroundColor Cyan
$backend = Start-Process -FilePath $python `
    -ArgumentList '-m', 'uvicorn', 'app.backend.main:app', '--port', $backendPort, '--reload' `
    -WorkingDirectory $root -PassThru

# Prima pornire poate dura: dacă lipsesc datele demo, backendul le descarcă și calculează
# detecția înainte de a răspunde.
Write-Host "     aștept ca backendul să răspundă (prima pornire poate dura un minut)..."
$ready = $false
foreach ($i in 1..90) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$backendPort/" -TimeoutSec 5 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { }
}
if (-not $ready) {
    Write-Warning "Backendul nu a răspuns în 3 minute. Verifică fereastra lui pentru erori."
} else {
    Write-Host "     backend gata." -ForegroundColor Green
}

Write-Host "2/3  Construiesc frontendul (cu API_BASE catre backendul local)..." -ForegroundColor Cyan
Push-Location $frontend
try {
    if (-not (Test-Path 'node_modules')) {
        Write-Host "     node_modules lipsește, rulez npm install..."
        npm install | Out-Null
    }
    $env:VITE_API_BASE = "http://localhost:$backendPort"
    npm run build | Out-Null
    Write-Host "     build gata." -ForegroundColor Green

    Write-Host "3/3  Servesc frontendul pe http://127.0.0.1:$frontendPort" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "     Deschide:  http://127.0.0.1:$frontendPort" -ForegroundColor Yellow
    Write-Host "     Oprire:    Ctrl+C" -ForegroundColor Yellow
    Write-Host ""
    npx vite preview --port $frontendPort --strictPort
}
finally {
    Pop-Location
    if ($backend -and -not $backend.HasExited) {
        Write-Host "Opresc backendul..." -ForegroundColor Cyan
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
